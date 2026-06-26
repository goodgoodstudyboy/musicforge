from __future__ import annotations

import argparse
import json
import shutil
import sys
import os
from pathlib import Path
from collections.abc import Callable
from typing import Any

from song_agent.agent.multinode_pipeline import generate_multinode_song_plan
from song_agent.agent.pipeline import SongAgent
from song_agent.agent.provider_pipeline import generate_provider_song_plan
from song_agent.auth import build_auth_config
from song_agent.node_store import NodeStore
from song_agent.projectio import ProjectPaths, default_run_dir, read_json, write_json
from song_agent.provider import (
    ProviderConfig,
    ProviderError,
    load_provider_config,
    provider_configured,
    test_provider_config,
)
from song_agent.quality import validate_song_plan
from song_agent.renderers.midi import render_midi
from song_agent.runtime import GraphRunner, PipelineStep, ResumeMismatchError
from song_agent.schemas.song import SongRequest
from song_agent.state import ArtifactRef, RunState


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a local MIDI song demo.")
    _add_generate_args(parser)
    return parser

def build_serve_parser() -> argparse.ArgumentParser:
    serve_parser = argparse.ArgumentParser(description="Start the local web panel.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    serve_parser.add_argument("--port", type=int, default=8787, help="Port to bind.")
    serve_parser.add_argument(
        "--access-token",
        default=None,
        help="Bearer token required for Studio/API access.",
    )
    return serve_parser

def build_generate_parser() -> argparse.ArgumentParser:
    generate_parser = argparse.ArgumentParser(
        description="Generate a MIDI song demo from a request JSON file."
    )
    _add_generate_args(generate_parser)
    return generate_parser


def build_doctor_parser() -> argparse.ArgumentParser:
    doctor_parser = argparse.ArgumentParser(description="Check the local MusicForge setup.")
    doctor_parser.add_argument(
        "--provider-test",
        action="store_true",
        help="Run the configured provider connectivity check.",
    )
    return doctor_parser


def build_release_check_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MusicForge release verification checks.")
    parser.add_argument("--profile", default="full", choices=["full", "quick", "latest", "v7", "v8", "v9", "v10", "ga", "publish"], help="Release-check profile to run.")
    parser.add_argument("--group", action="append", default=[], help="Run checks matching this group or tag. Can be repeated.")
    parser.add_argument("--since", default=None, help="Run versioned checks from this version onward, for example 7.0.")
    parser.add_argument("--only", action="append", default=[], help="Run only one or more check ids. Comma-separated values are accepted.")
    parser.add_argument("--list", action="store_true", help="List selected checks without running them.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON report.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write the JSON report to this path.")
    parser.add_argument("--timing-out", type=Path, default=None, help="Write a lightweight timing report to this path.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed check.")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Override per-command timeout. Minimum is 10 seconds.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip the full pytest check when selected.")
    return parser


def build_ga_check_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MusicForge GA/LTS readiness checks.")
    parser.add_argument("--json", action="store_true", help="Print the full GA readiness report as JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write the GA readiness report to this JSON file.")
    parser.add_argument("--strict", action="store_true", help="Treat a dirty working tree and missing required evidence as blocking.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow dirty working tree as a warning even with --strict.")
    parser.add_argument("--require-manual-acceptance", action="store_true", help="Require manual listening acceptance evidence.")
    parser.add_argument("--require-audio", action="store_true", help="Require renderer/audio acceptance readiness.")
    parser.add_argument("--require-final-readiness", action="store_true", help="Require a passed Final Handoff verification report.")
    parser.add_argument("--final-handoff-verification-report", type=Path, default=None, help="Path to Final Handoff verification report JSON.")
    parser.add_argument("--require-audio-campaign", dest="audio_campaign_id", default=None, help="Require a signed Audio Campaign id.")
    parser.add_argument("--audio-campaign-archive", type=Path, default=None, help="Path to Audio Campaign Archive ZIP.")
    parser.add_argument("--audio-campaign-archive-verification-report", type=Path, default=None, help="Path to Audio Campaign Archive verification report JSON.")
    parser.add_argument("--require-audio-campaign-remediation", action="store_true", help="Require passed Release Audio Campaign remediation evidence.")
    parser.add_argument("--audio-campaign-remediation", type=Path, default=None, help="Path to Release Audio Campaign Remediation ZIP.")
    parser.add_argument("--audio-campaign-remediation-verification-report", type=Path, default=None, help="Path to Release Audio Campaign Remediation verification report JSON.")
    parser.add_argument("--release-check-latest-report", type=Path, default=None, help="Path to an existing latest release-check JSON report.")
    parser.add_argument("--release-check-ga-report", type=Path, default=None, help="Path to an existing ga release-check JSON report.")
    parser.add_argument("--run-release-checks", action="store_true", help="Run latest and ga release-check profiles during ga-check.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip full pytest if --run-release-checks selects it.")
    return parser


def build_verify_ga_readiness_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge GA readiness report.")
    parser.add_argument("report_path", type=Path, help="Path to ga-readiness-report.json.")
    parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    parser.add_argument("--strict", action="store_true", help="Require GA status ready, not warning.")
    parser.add_argument("--require-ready", action="store_true", help="Require GA readiness status ready.")
    parser.add_argument("--require-manual-acceptance", action="store_true", help="Require external manual acceptance evidence.")
    parser.add_argument("--manual-acceptance-report", type=Path, default=None, help="External music acceptance report JSON to bind manual readiness.")
    parser.add_argument("--require-final-readiness", action="store_true", help="Require external final readiness evidence.")
    parser.add_argument("--final-handoff-package", type=Path, default=None, help="External Trust Operations Final Handoff ZIP.")
    parser.add_argument("--final-handoff-verification-report", type=Path, default=None, help="External Trust Operations Final Handoff verification report JSON.")
    parser.add_argument("--require-audio-campaign", action="store_true", help="Require external Audio Campaign governance evidence.")
    parser.add_argument("--audio-campaign-archive", type=Path, default=None, help="External Audio Campaign Archive ZIP.")
    parser.add_argument("--audio-campaign-archive-verification-report", type=Path, default=None, help="External Audio Campaign Archive verification report JSON.")
    parser.add_argument("--require-audio-campaign-remediation", action="store_true", help="Require external Audio Campaign remediation evidence.")
    parser.add_argument("--audio-campaign-remediation", type=Path, default=None, help="External Audio Campaign Remediation ZIP.")
    parser.add_argument("--audio-campaign-remediation-verification-report", type=Path, default=None, help="External Audio Campaign Remediation verification report JSON.")
    return parser


def build_maintenance_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local MusicForge LTS maintenance, backups, upgrades, and checks.")
    subparsers = parser.add_subparsers(dest="section", required=True)

    status = subparsers.add_parser("status", help="Show local LTS maintenance status.")
    status.add_argument("--json", action="store_true", help="Print JSON output.")

    backup = subparsers.add_parser("backup", help="Create, verify, and restore maintenance backups.")
    backup_sub = backup.add_subparsers(dest="backup_action", required=True)
    create = backup_sub.add_parser("create", help="Create a maintenance backup.")
    create.add_argument("--mode", choices=["metadata", "workspace", "workspace_with_artifacts"], default="workspace")
    create.add_argument("--json", action="store_true")
    listing = backup_sub.add_parser("list", help="List maintenance backups.")
    listing.add_argument("--json", action="store_true")
    verify = backup_sub.add_parser("verify", help="Verify a maintenance backup by id.")
    verify.add_argument("--backup-id", required=True)
    verify.add_argument("--json", action="store_true")
    restore_plan = backup_sub.add_parser("restore-plan", help="Create a restore plan from a backup.")
    restore_plan.add_argument("--backup-id", default=None)
    restore_plan.add_argument("--zip", dest="zip_path", type=Path, default=None)
    restore_plan.add_argument("--target", type=Path, required=True)
    restore_plan.add_argument("--json", action="store_true")
    restore = backup_sub.add_parser("restore", help="Restore a backup into a target directory.")
    restore.add_argument("--backup-id", default=None)
    restore.add_argument("--zip", dest="zip_path", type=Path, default=None)
    restore.add_argument("--target", type=Path, required=True)
    restore.add_argument("--confirm", action="store_true")
    restore.add_argument("--overwrite", action="store_true")
    restore.add_argument("--allow-current-workspace", action="store_true")
    restore.add_argument("--json", action="store_true")

    upgrade = subparsers.add_parser("upgrade", help="Run upgrade preflight checks.")
    upgrade_sub = upgrade.add_subparsers(dest="upgrade_action", required=True)
    preflight = upgrade_sub.add_parser("preflight", help="Run upgrade preflight checks.")
    preflight.add_argument("--target-version", required=True)
    preflight.add_argument("--require-verified-backup", action="store_true")
    preflight.add_argument("--allow-dirty", action="store_true")
    preflight.add_argument("--json", action="store_true")

    migration = subparsers.add_parser("migration", help="Manage local LTS migrations.")
    migration_sub = migration.add_subparsers(dest="migration_action", required=True)
    migration_sub.add_parser("status", help="Show migration status.").add_argument("--json", action="store_true")
    migration_sub.add_parser("plan", help="Show pending migrations.").add_argument("--json", action="store_true")
    migration_run = migration_sub.add_parser("run", help="Run pending migrations.")
    migration_run.add_argument("--require-backup", action="store_true")
    migration_run.add_argument("--json", action="store_true")

    check = subparsers.add_parser("check", help="Run periodic maintenance checks.")
    check_sub = check.add_subparsers(dest="check_action", required=True)
    check_list = check_sub.add_parser("list", help="List maintenance check profiles and prior runs.")
    check_list.add_argument("--json", action="store_true")
    check_run = check_sub.add_parser("run", help="Run a maintenance check profile.")
    check_run.add_argument("--profile", choices=["daily", "weekly", "release", "emergency"], default="daily")
    check_run.add_argument("--json", action="store_true")
    check_show = check_sub.add_parser("show", help="Show a maintenance check report.")
    check_show.add_argument("--check-id", required=True)
    check_show.add_argument("--json", action="store_true")
    return parser


def build_audio_lab_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MusicForge Audio Lab environment, smoke, listening, and A/B checks.")
    subparsers = parser.add_subparsers(dest="section", required=True)

    status = subparsers.add_parser("status", help="Show Audio Lab environment status.")
    status.add_argument("--json", action="store_true")

    detect = subparsers.add_parser("detect", help="Detect local Audio Lab renderer readiness.")
    detect.add_argument("--json", action="store_true")

    test_profile = subparsers.add_parser("test-profile", help="Test the configured renderer profile.")
    test_profile.add_argument("--profile", "--profile-id", dest="profile_id", default=None)
    test_profile.add_argument("--json", action="store_true")

    setup_report = subparsers.add_parser("setup-report", help="Write and show the Audio Lab setup report.")
    setup_report.add_argument("--json", action="store_true")
    setup_report.add_argument("--report-out", type=Path, default=None)

    smoke = subparsers.add_parser("smoke", help="Create an Audio Lab smoke run.")
    smoke.add_argument("--cases", type=int, default=1)
    smoke.add_argument("--render-audio", choices=["auto", "required", "require", "never"], default="auto")
    smoke.add_argument("--profile", "--profile-id", dest="profile_id", default=None)
    smoke.add_argument("--json", action="store_true")
    smoke.add_argument("--report-out", type=Path, default=None)

    smoke_report = subparsers.add_parser("smoke-report", help="Show an Audio Lab smoke run report.")
    smoke_report.add_argument("smoke_run_id")
    smoke_report.add_argument("--json", action="store_true")
    smoke_report.add_argument("--report-out", type=Path, default=None)

    session = subparsers.add_parser("session", help="Manage Audio Lab listening sessions.")
    session_sub = session.add_subparsers(dest="session_action", required=True)
    session_create = session_sub.add_parser("create", help="Create a listening session from a smoke run.")
    session_create.add_argument("--from-smoke", required=True)
    session_create.add_argument("--json", action="store_true")
    session_list = session_sub.add_parser("list", help="List listening sessions.")
    session_list.add_argument("--json", action="store_true")
    session_detail = session_sub.add_parser("detail", help="Show a listening session.")
    session_detail.add_argument("session_id")
    session_detail.add_argument("--json", action="store_true")
    session_review = session_sub.add_parser("review", help="Write a manual listening review.")
    session_review.add_argument("session_id")
    session_review.add_argument("item_id")
    session_review.add_argument("--result", choices=["accepted", "needs_fix", "rejected"], required=True)
    session_review.add_argument("--rating", type=int, required=True)
    session_review.add_argument("--reviewer", default="developer")
    session_review.add_argument("--role", default="developer")
    session_review.add_argument("--notes", default="")
    session_review.add_argument("--playback-confirmed", action="store_true")
    session_review.add_argument("--json", action="store_true")
    session_marker = session_sub.add_parser("marker", help="Add an issue marker to a listening item.")
    session_marker.add_argument("session_id")
    session_marker.add_argument("item_id")
    session_marker.add_argument("--time-seconds", type=float, default=0.0)
    session_marker.add_argument("--category", default="other")
    session_marker.add_argument("--severity", default="medium")
    session_marker.add_argument("--message", default="")
    session_marker.add_argument("--json", action="store_true")
    session_task = session_sub.add_parser("create-review-task", help="Create a draft ReviewTask from a marker.")
    session_task.add_argument("session_id")
    session_task.add_argument("marker_id")
    session_task.add_argument("--title", default="")
    session_task.add_argument("--instruction", default="")
    session_task.add_argument("--json", action="store_true")
    session_revision = session_sub.add_parser("create-audio-revision-draft", help="Create an Audio Revision draft from a marker.")
    session_revision.add_argument("session_id")
    session_revision.add_argument("marker_id")
    session_revision.add_argument("--title", default="")
    session_revision.add_argument("--instruction", default="")
    session_revision.add_argument("--json", action="store_true")
    session_mix = session_sub.add_parser("create-mix-patch-draft", help="Create a Mix Patch draft from a marker.")
    session_mix.add_argument("session_id")
    session_mix.add_argument("marker_id")
    session_mix.add_argument("--title", default="")
    session_mix.add_argument("--instruction", default="")
    session_mix.add_argument("--json", action="store_true")
    session_report = session_sub.add_parser("report", help="Write and show a listening session report.")
    session_report.add_argument("session_id")
    session_report.add_argument("--json", action="store_true")
    session_close = session_sub.add_parser("close", help="Close a reviewed listening session.")
    session_close.add_argument("session_id")
    session_close.add_argument("--closed-by", default="audio-lab")
    session_close.add_argument("--json", action="store_true")

    compare = subparsers.add_parser("compare", help="Manage Audio Lab A/B comparisons.")
    compare_sub = compare.add_subparsers(dest="compare_action", required=True)
    compare_create = compare_sub.add_parser("create", help="Create an A/B comparison.")
    compare_create.add_argument("--left", required=True)
    compare_create.add_argument("--right", required=True)
    compare_create.add_argument("--json", action="store_true")
    compare_review = compare_sub.add_parser("review", help="Review an A/B comparison.")
    compare_review.add_argument("comparison_id")
    compare_review.add_argument("--preferred", choices=["left", "right", "same"], required=True)
    compare_review.add_argument("--rating", type=int, default=4)
    compare_review.add_argument("--rating-delta", type=int, default=0)
    compare_review.add_argument("--reviewer", default="developer")
    compare_review.add_argument("--role", default="developer")
    compare_review.add_argument("--notes", default="")
    compare_review.add_argument("--playback-confirmed", action="store_true")
    compare_review.add_argument("--json", action="store_true")
    compare_report = compare_sub.add_parser("report", help="Write and show an A/B comparison report.")
    compare_report.add_argument("comparison_id")
    compare_report.add_argument("--json", action="store_true")
    return parser


def build_audio_fix_sprint_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Audio Fix Sprints from Audio Lab needs_fix markers.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="Create a sprint from one or more Audio Lab sessions.")
    create.add_argument("--from-session", "--session-id", dest="session_ids", action="append", required=True)
    create.add_argument("--name", default="")
    create.add_argument("--include-test-audio", action="store_true")
    create.add_argument("--json", action="store_true")

    listing = subparsers.add_parser("list", help="List Audio Fix Sprints.")
    listing.add_argument("--json", action="store_true")

    detail = subparsers.add_parser("detail", help="Show one Audio Fix Sprint.")
    detail.add_argument("sprint_id")
    detail.add_argument("--json", action="store_true")

    refresh = subparsers.add_parser("refresh", help="Refresh stale status for an Audio Fix Sprint.")
    refresh.add_argument("sprint_id")
    refresh.add_argument("--json", action="store_true")

    drafts = subparsers.add_parser("create-drafts", help="Create deterministic fix drafts for sprint items.")
    drafts.add_argument("sprint_id")
    drafts.add_argument("--draft-type", choices=["review_task", "audio_revision", "mix_patch"], default="review_task")
    drafts.add_argument("--item-id", dest="item_ids", action="append")
    drafts.add_argument("--json", action="store_true")

    candidates = subparsers.add_parser("generate-candidates", help="Generate local deterministic fix candidates.")
    candidates.add_argument("sprint_id")
    candidates.add_argument("--item-id", dest="item_ids", action="append")
    candidates.add_argument("--json", action="store_true")

    review = subparsers.add_parser("review-candidate", help="Write a manual A/B review for a candidate.")
    review.add_argument("sprint_id")
    review.add_argument("item_id")
    review.add_argument("candidate_id")
    review.add_argument("--preferred", choices=["left", "right", "same"], required=True)
    review.add_argument("--rating", type=int, default=4)
    review.add_argument("--rating-delta", type=int, default=0)
    review.add_argument("--reviewer", default="developer")
    review.add_argument("--role", default="developer")
    review.add_argument("--notes", default="")
    review.add_argument("--playback-confirmed", action="store_true")
    review.add_argument("--json", action="store_true")

    select = subparsers.add_parser("select-candidate", help="Select a manually reviewed candidate.")
    select.add_argument("sprint_id")
    select.add_argument("item_id")
    select.add_argument("candidate_id")
    select.add_argument("--selected-by", default="audio-fix-sprint")
    select.add_argument("--json", action="store_true")

    recheck = subparsers.add_parser("create-recheck-session", help="Create the manual recheck session from selected candidates.")
    recheck.add_argument("sprint_id")
    recheck.add_argument("--json", action="store_true")

    recheck_review = subparsers.add_parser("review-recheck", help="Review one recheck session item.")
    recheck_review.add_argument("sprint_id")
    recheck_review.add_argument("item_id")
    recheck_review.add_argument("--result", choices=["accepted", "needs_fix", "rejected"], required=True)
    recheck_review.add_argument("--rating", type=int, default=4)
    recheck_review.add_argument("--reviewer", default="developer")
    recheck_review.add_argument("--role", default="developer")
    recheck_review.add_argument("--notes", default="")
    recheck_review.add_argument("--playback-confirmed", action="store_true")
    recheck_review.add_argument("--json", action="store_true")

    closeout = subparsers.add_parser("closeout", help="Build and show the Audio Fix Sprint closeout report.")
    closeout.add_argument("sprint_id")
    closeout.add_argument("--json", action="store_true")

    close = subparsers.add_parser("close", help="Close a sprint after manual A/B and accepted recheck.")
    close.add_argument("sprint_id")
    close.add_argument("--closed-by", default="audio-fix-sprint")
    close.add_argument("--json", action="store_true")
    return parser


def build_audio_campaign_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage release candidate Audio Campaigns from Audio Lab sessions.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="Create an Audio Campaign from one or more Audio Lab sessions.")
    create.add_argument("--from-session", "--session-id", dest="session_ids", action="append", required=True)
    create.add_argument("--name", default="")
    create.add_argument("--profile", default="release_candidate")
    create.add_argument("--allow-test-audio", action="store_true")
    create.add_argument("--allow-synthetic-review", action="store_true")
    create.add_argument("--minimum-rating", type=int, default=4)
    create.add_argument("--json", action="store_true")

    listing = subparsers.add_parser("list", help="List Audio Campaigns.")
    listing.add_argument("--json", action="store_true")

    detail = subparsers.add_parser("detail", help="Show one Audio Campaign.")
    detail.add_argument("campaign_id")
    detail.add_argument("--json", action="store_true")

    refresh = subparsers.add_parser("refresh", help="Refresh Audio Campaign source snapshots.")
    refresh.add_argument("campaign_id")
    refresh.add_argument("--json", action="store_true")

    link_session = subparsers.add_parser("link-session", help="Add another Audio Lab listening session to a campaign.")
    link_session.add_argument("campaign_id")
    link_session.add_argument("--session-id", required=True)
    link_session.add_argument("--json", action="store_true")

    fix_sprints = subparsers.add_parser("create-fix-sprints", help="Create Audio Fix Sprints for campaign issues.")
    fix_sprints.add_argument("campaign_id")
    fix_sprints.add_argument("--json", action="store_true")

    report = subparsers.add_parser("report", help="Build and show the Audio Campaign report.")
    report.add_argument("campaign_id")
    report.add_argument("--json", action="store_true")

    signoff = subparsers.add_parser("signoff", help="Sign off a passed Audio Campaign.")
    signoff.add_argument("campaign_id")
    signoff.add_argument("--signed-by", required=True)
    signoff.add_argument("--role", default="audio-reviewer")
    signoff.add_argument("--reason", default="")
    signoff.add_argument("--json", action="store_true")

    export = subparsers.add_parser("export", help="Export the Audio Campaign evidence package directory.")
    export.add_argument("campaign_id")
    export.add_argument("--json", action="store_true")

    zip_cmd = subparsers.add_parser("zip", help="Build the Audio Campaign ZIP.")
    zip_cmd.add_argument("campaign_id")
    zip_cmd.add_argument("--json", action="store_true")

    verify = subparsers.add_parser("verify", help="Verify the Audio Campaign ZIP.")
    verify.add_argument("campaign_id")
    verify.add_argument("--strict", action="store_true")
    verify.add_argument("--require-real-audio", action="store_true")
    verify.add_argument("--require-manual-review", action="store_true")
    verify.add_argument("--require-fix-sprints-closed", action="store_true")
    verify.add_argument("--require-signed", action="store_true")
    verify.add_argument("--json", action="store_true")
    verify.add_argument("--report-out", type=Path, default=None)

    governance = subparsers.add_parser("governance", help="Refresh the Audio Campaign governance report.")
    governance.add_argument("campaign_id")
    governance.add_argument("--json", action="store_true")

    analytics = subparsers.add_parser("analytics", help="Refresh the Audio Campaign analytics summary.")
    analytics.add_argument("campaign_id")
    analytics.add_argument("--json", action="store_true")

    archive = subparsers.add_parser("archive", help="Export signed Audio Campaign governance archive files.")
    archive.add_argument("campaign_id")
    archive.add_argument("--json", action="store_true")

    archive_zip = subparsers.add_parser("archive-zip", help="Build the signed Audio Campaign governance archive ZIP.")
    archive_zip.add_argument("campaign_id")
    archive_zip.add_argument("--json", action="store_true")

    verify_archive = subparsers.add_parser("verify-archive", help="Verify the signed Audio Campaign governance archive ZIP.")
    verify_archive.add_argument("campaign_id")
    verify_archive.add_argument("--strict", action="store_true")
    verify_archive.add_argument("--json", action="store_true")
    verify_archive.add_argument("--report-out", type=Path, default=None)

    remediation_plan = subparsers.add_parser("remediation-plan", help="Refresh Release Audio Campaign remediation plan.")
    remediation_plan.add_argument("release_id")
    remediation_plan.add_argument("--json", action="store_true")

    remediation_status = subparsers.add_parser("remediation-status", help="Show Release Audio Campaign remediation status.")
    remediation_status.add_argument("release_id")
    remediation_status.add_argument("--json", action="store_true")

    remediation_run = subparsers.add_parser("remediation-run-safe", help="Run safe remediation actions.")
    remediation_run.add_argument("release_id")
    remediation_run.add_argument("--closed-by", default="audio-campaign-remediation")
    remediation_run.add_argument("--json", action="store_true")

    remediation_closeout = subparsers.add_parser("remediation-closeout", help="Build Release Audio Campaign remediation closeout report.")
    remediation_closeout.add_argument("release_id")
    remediation_closeout.add_argument("--json", action="store_true")

    remediation_signoff = subparsers.add_parser("remediation-signoff", help="Sign off passed Release Audio Campaign remediation evidence.")
    remediation_signoff.add_argument("release_id")
    remediation_signoff.add_argument("--signed-by", required=True)
    remediation_signoff.add_argument("--role", default="audio-remediation-reviewer")
    remediation_signoff.add_argument("--reason", default="")
    remediation_signoff.add_argument("--json", action="store_true")

    remediation_export = subparsers.add_parser("remediation-export", help="Export Release Audio Campaign remediation evidence.")
    remediation_export.add_argument("release_id")
    remediation_export.add_argument("--json", action="store_true")

    remediation_zip = subparsers.add_parser("remediation-zip", help="Build Release Audio Campaign remediation ZIP.")
    remediation_zip.add_argument("release_id")
    remediation_zip.add_argument("--json", action="store_true")

    remediation_verify = subparsers.add_parser("remediation-verify", help="Verify Release Audio Campaign remediation ZIP.")
    remediation_verify.add_argument("release_id")
    remediation_verify.add_argument("--strict", action="store_true")
    remediation_verify.add_argument("--require-passed", action="store_true")
    remediation_verify.add_argument("--require-signed", action="store_true")
    remediation_verify.add_argument("--json", action="store_true")
    remediation_verify.add_argument("--report-out", type=Path, default=None)

    cr_create = subparsers.add_parser("change-request-create", help="Create an Audio Campaign signoff reset Change Request.")
    cr_create.add_argument("campaign_id")
    cr_create.add_argument("--created-by", default="developer")
    cr_create.add_argument("--reason", required=True)
    cr_create.add_argument("--risk", default="medium")
    cr_create.add_argument("--json", action="store_true")

    cr_approve = subparsers.add_parser("change-request-approve", help="Approve an Audio Campaign signoff reset Change Request.")
    cr_approve.add_argument("campaign_id")
    cr_approve.add_argument("change_request_id")
    cr_approve.add_argument("--approved-by", default="reviewer")
    cr_approve.add_argument("--reason", default="")
    cr_approve.add_argument("--json", action="store_true")

    reset = subparsers.add_parser("signoff-reset", help="Reset Audio Campaign signoff with an approved Change Request.")
    reset.add_argument("campaign_id")
    reset.add_argument("--change-request-id", required=True)
    reset.add_argument("--reason", required=True)
    reset.add_argument("--json", action="store_true")

    plan_release = subparsers.add_parser("plan-release", help="Create or refresh a release-bound Audio Campaign plan.")
    plan_release.add_argument("release_id")
    plan_release.add_argument("--json", action="store_true")

    preflight_release = subparsers.add_parser("preflight-release", help="Run Release Audio Campaign preflight.")
    preflight_release.add_argument("release_id")
    preflight_release.add_argument("--json", action="store_true")

    create_from_release = subparsers.add_parser("create-from-release", help="Create Audio Lab session and Audio Campaign from Release tracks.")
    create_from_release.add_argument("release_id")
    create_from_release.add_argument("--name", default="")
    create_from_release.add_argument("--minimum-rating", type=int, default=4)
    create_from_release.add_argument("--allow-failed-preflight", action="store_true")
    create_from_release.add_argument("--json", action="store_true")

    release_status = subparsers.add_parser("release-status", help="Show Release Audio Campaign plan status.")
    release_status.add_argument("release_id")
    release_status.add_argument("--json", action="store_true")

    release_link = subparsers.add_parser("release-link", help="Link an existing Audio Campaign to a Release plan.")
    release_link.add_argument("release_id")
    release_link.add_argument("--campaign-id", required=True)
    release_link.add_argument("--json", action="store_true")
    return parser


def build_verify_audio_campaign_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Audio Campaign ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-real-audio", action="store_true")
    parser.add_argument("--require-manual-review", action="store_true")
    parser.add_argument("--require-fix-sprints-closed", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-no-open-high", action="store_true")
    parser.add_argument("--require-no-open-critical", action="store_true")
    parser.add_argument("--max-zip-size-mb", type=int, default=256)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=5000)
    return parser


def build_verify_audio_campaign_archive_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Audio Campaign Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-verification-passed", action="store_true")
    parser.add_argument("--max-zip-size-mb", type=int, default=256)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=5000)
    return parser


def build_verify_audio_campaign_remediation_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Audio Campaign Remediation ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-passed", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser


def build_verify_maintenance_backup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge LTS maintenance backup ZIP.")
    parser.add_argument("zip_path", type=Path, help="Path to musicforge-maintenance-backup.zip.")
    parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    parser.add_argument("--strict", action="store_true", help="Run strict verification.")
    parser.add_argument("--max-zip-size-mb", type=int, default=512)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=2048)
    parser.add_argument("--max-entry-count", type=int, default=20000)
    return parser


def build_verify_release_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict-order warnings as failures.")
    verify_parser.add_argument("--require-audio", action="store_true", help="Require each track to include song.wav.")
    verify_parser.add_argument("--require-human-review", action="store_true", help="Require release signoff to include manual WAV review evidence.")
    verify_parser.add_argument("--require-audio-revisions", action="store_true", help="Require Audio Revision Workbench closeout evidence.")
    verify_parser.add_argument("--require-stems", action="store_true", help="Require each track to include a stems manifest and declared stem MIDI files.")
    verify_parser.add_argument("--require-mastering", action="store_true", help="Require Mastering QA and selected mastered WAV evidence.")
    verify_parser.add_argument("--require-encoded-audio", action="store_true", help="Require encoded audio summary evidence.")
    verify_parser.add_argument("--require-encoded-audio-review", action="store_true", help="Require manual encoded audio review evidence.")
    verify_parser.add_argument("--require-format-decision", action="store_true", help="Require Release Format Decision evidence.")
    verify_parser.add_argument("--require-rights-clearance", action="store_true", help="Require Rights Clearance evidence.")
    verify_parser.add_argument("--require-audio-formats", default="", help="Comma-separated encoded audio profile ids to require.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=512, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=2048, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_distribution_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Distribution Package ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Distribution Package ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-audio", action="store_true", help="Require exported package layout audio files.")
    verify_parser.add_argument("--require-artwork", action="store_true", help="Require exported package artwork.")
    verify_parser.add_argument("--require-encoded-audio", action="store_true", help="Require encoded audio evidence for package audio files.")
    verify_parser.add_argument("--require-encoded-audio-review", action="store_true", help="Require manual encoded audio review evidence for encoded package audio.")
    verify_parser.add_argument("--require-format-decision", action="store_true", help="Require Distribution format decision evidence.")
    verify_parser.add_argument("--require-rights-clearance", action="store_true", help="Require Rights Clearance evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=512, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=2048, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_submission_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Submission Package ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Submission Package ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-submitted", action="store_true", help="Require every item to have submitted-or-later status.")
    verify_parser.add_argument("--require-accepted", action="store_true", help="Require every item to be accepted.")
    verify_parser.add_argument("--require-rights-clearance", action="store_true", help="Require Rights Clearance evidence.")
    verify_parser.add_argument("--deep", action="store_true", help="Run the Distribution Package verifier on nested target ZIP files.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=1024, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=4096, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=10000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_submission_evidence_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Submission Evidence Package ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Submission Evidence Package ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--deep", action="store_true", help="Run the Submission Package verifier on the nested submission ZIP.")
    verify_parser.add_argument("--require-submitted", action="store_true", help="Require every item to have submitted-or-later evidence.")
    verify_parser.add_argument("--require-accepted", action="store_true", help="Require every item to be accepted.")
    verify_parser.add_argument("--require-rights-clearance", action="store_true", help="Require nested Rights Clearance evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=1024, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=4096, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=10000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_operations_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Operations Package ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Operations ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-accepted", action="store_true", help="Require Operations current_stage to be accepted or archived.")
    verify_parser.add_argument("--require-submission-evidence", action="store_true", help="Require the Submission Evidence domain to be ready.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_release_operations_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build local MusicForge Release Operations reports and packages.")
    parser.add_argument("--release-id", required=True, help="Release id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh and persist the Operations Report.")
    parser.add_argument("--export", action="store_true", help="Build the Operations Export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Operations ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Operations ZIP package.")
    parser.add_argument("--require-accepted", action="store_true", help="When verifying, require accepted stage.")
    parser.add_argument("--require-submission-evidence", action="store_true", help="When verifying, require Submission Evidence readiness.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_verify_release_operations_runbook_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Operations Runbook Package ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Operations Runbook ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-completed", action="store_true", help="Require completed or blocked runbook evidence with no failed auto-safe item.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require the exported runbook to be current.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_operations_archive_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Operations Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Operations Archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Operations Signoff evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_operations_audit_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Operations Audit ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Operations Audit ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current passed/warning Audit Report evidence.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Operations Signoff evidence.")
    verify_parser.add_argument("--require-archive", action="store_true", help="Require Operations Archive evidence in the ledger.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_operations_reviewer_pack_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Operations Reviewer Pack ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Operations Reviewer Pack ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-audit", action="store_true", help="Require usable Audit evidence.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Operations Signoff evidence.")
    verify_parser.add_argument("--require-archive", action="store_true", help="Require verified Operations Archive evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_audit_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Audit ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Audit ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-reviewer-packs", action="store_true", help="Require passed Reviewer Pack verification for every release.")
    verify_parser.add_argument("--require-audit", action="store_true", help="Require passed Audit package verification for every release.")
    verify_parser.add_argument("--require-archive", action="store_true", help="Require passed Operations Archive verification for every release.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Queue ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Queue ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-manual-actions", action="store_true", help="Require manual-action-list coverage for manual-required items.")
    verify_parser.add_argument("--require-no-blocked", action="store_true", help="Fail when blocked or failed queue items remain.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_archive_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Governance Signoff evidence.")
    verify_parser.add_argument("--require-no-force", action="store_true", help="Fail when Governance Signoff was force signed.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_release_operations_runbook_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and run local MusicForge Release Operations Runbooks.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--runbook-id", default="", help="Runbook id for detail/run/export actions.")
    parser.add_argument("--create", action="store_true", help="Create a runbook from the current Operations Report.")
    parser.add_argument("--list", action="store_true", help="List runbooks.")
    parser.add_argument("--run-safe", action="store_true", help="Run auto-safe actions.")
    parser.add_argument("--refresh-stale", action="store_true", help="Refresh stale status.")
    parser.add_argument("--export", action="store_true", help="Export runbook evidence.")
    parser.add_argument("--zip", action="store_true", help="Build runbook evidence ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify runbook ZIP.")
    parser.add_argument("--archive", action="store_true", help="Archive the runbook.")
    parser.add_argument("--require-completed", action="store_true", help="When verifying, require completed runbook evidence.")
    parser.add_argument("--require-current", action="store_true", help="When verifying, require current runbook evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_operations_signoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sign or reset local MusicForge Release Operations archive evidence.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--sign", action="store_true", help="Create Operations Signoff.")
    parser.add_argument("--reset", action="store_true", help="Reset Operations Signoff.")
    parser.add_argument("--signed-by", default="local-user", help="Signer name.")
    parser.add_argument("--force", action="store_true", help="Force signoff through non-hard warnings.")
    parser.add_argument("--override-reason", default="", help="Required with --force when warnings are force accepted.")
    parser.add_argument("--reason", default="", help="Reset reason.")
    parser.add_argument("--change-request-id", default="", help="Approved change request id for reset.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_operations_archive_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export and verify local MusicForge Release Operations Archive packages.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--export", action="store_true", help="Build Operations Archive export directory.")
    parser.add_argument("--zip", action="store_true", help="Build Operations Archive ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify Operations Archive ZIP.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-signed", action="store_true", help="Require signed Operations Signoff evidence when verifying.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_operations_audit_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Operations Audit ledger packages.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Operations Audit ledger and report.")
    parser.add_argument("--entries", action="store_true", help="List ledger entries.")
    parser.add_argument("--graph", action="store_true", help="Print graph summary.")
    parser.add_argument("--export", action="store_true", help="Build Operations Audit export directory.")
    parser.add_argument("--zip", action="store_true", help="Build Operations Audit ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify Operations Audit ZIP.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-current", action="store_true", help="Require current Audit Report evidence when verifying.")
    parser.add_argument("--require-signed", action="store_true", help="Require signed Operations Signoff evidence when verifying.")
    parser.add_argument("--require-archive", action="store_true", help="Require Operations Archive evidence when verifying.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_operations_reviewer_pack_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Operations Reviewer Packs.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh Reviewer Report and Retrospective.")
    parser.add_argument("--export", action="store_true", help="Build Reviewer Pack export directory.")
    parser.add_argument("--zip", action="store_true", help="Build Reviewer Pack ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify Reviewer Pack ZIP.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-audit", action="store_true", help="Require usable Audit evidence when verifying.")
    parser.add_argument("--require-signed", action="store_true", help="Require signed Operations Signoff evidence when verifying.")
    parser.add_argument("--require-archive", action="store_true", help="Require verified Operations Archive evidence when verifying.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_audit_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Portfolio Audits.")
    parser.add_argument("--portfolio-id", default="", help="Portfolio Audit id.")
    parser.add_argument("--list", action="store_true", help="List Portfolio Audits.")
    parser.add_argument("--create", action="store_true", help="Create a Portfolio Audit.")
    parser.add_argument("--name", default="", help="Portfolio name when creating.")
    parser.add_argument("--release-ids", default="", help="Comma-separated Release ids to include. Empty means all releases.")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden releases.")
    parser.add_argument("--exclude-archived", action="store_true", help="Exclude archived releases.")
    parser.add_argument("--max-releases", type=int, default=None, help="Maximum number of releases to include.")
    parser.add_argument("--refresh", action="store_true", help="Refresh Portfolio Audit reports.")
    parser.add_argument("--export", action="store_true", help="Build Portfolio Audit export directory.")
    parser.add_argument("--zip", action="store_true", help="Build Portfolio Audit ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify Portfolio Audit ZIP.")
    parser.add_argument("--archive", action="store_true", help="Archive the Portfolio Audit.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-reviewer-packs", action="store_true", help="Require passed Reviewer Pack verification.")
    parser.add_argument("--require-audit", action="store_true", help="Require passed Audit package verification.")
    parser.add_argument("--require-archive", action="store_true", help="Require passed Operations Archive verification.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_governance_queue_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and run local MusicForge Release Portfolio Governance Queues.")
    parser.add_argument("--queue-id", default="", help="Governance Queue id.")
    parser.add_argument("--portfolio-id", default="", help="Portfolio Audit id.")
    parser.add_argument("--list", action="store_true", help="List Governance Queues.")
    parser.add_argument("--create", action="store_true", help="Create a Governance Queue from the current Portfolio Audit report.")
    parser.add_argument("--name", default="", help="Queue name when creating.")
    parser.add_argument("--force-new", action="store_true", help="Create a new queue even when an open queue already exists for the same source.")
    parser.add_argument("--run-safe", action="store_true", help="Run auto-safe governance actions.")
    parser.add_argument("--refresh-portfolio-after-safe-actions", action="store_true", help="Refresh Portfolio Audit after safe actions change underlying evidence.")
    parser.add_argument("--export", action="store_true", help="Build Governance Queue export directory.")
    parser.add_argument("--zip", action="store_true", help="Build Governance Queue ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify Governance Queue ZIP.")
    parser.add_argument("--archive", action="store_true", help="Archive the Governance Queue.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-manual-actions", action="store_true", help="Require manual-action-list coverage when verifying.")
    parser.add_argument("--require-no-blocked", action="store_true", help="Fail verification when blocked or failed items remain.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_governance_signoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sign, reset, and archive local MusicForge Release Portfolio Governance Queue evidence.")
    parser.add_argument("--queue-id", required=True, help="Governance Queue id.")
    parser.add_argument("--sign", action="store_true", help="Create Portfolio Governance Signoff.")
    parser.add_argument("--reset", action="store_true", help="Reset Portfolio Governance Signoff.")
    parser.add_argument("--signed-by", default="local-user", help="Signer name.")
    parser.add_argument("--force", action="store_true", help="Force signoff through manual acknowledgement warnings.")
    parser.add_argument("--override-reason", default="", help="Required with --force.")
    parser.add_argument("--reason", default="", help="Change Request or reset reason.")
    parser.add_argument("--change-request-id", default="", help="Approved Change Request id for reset.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Governance Change Request.")
    parser.add_argument("--approve-change-request", default="", help="Approve a Governance Change Request id.")
    parser.add_argument("--reject-change-request", default="", help="Reject a Governance Change Request id.")
    parser.add_argument("--approved-by", default="local-user", help="Approver name.")
    parser.add_argument("--export-archive", action="store_true", help="Build Governance Archive export directory.")
    parser.add_argument("--zip", action="store_true", help="Build Governance Archive ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify Governance Archive ZIP.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-signed", action="store_true", help="Require signed Governance Signoff when verifying.")
    parser.add_argument("--require-no-force", action="store_true", help="Fail verification when signoff is force signed.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_governance_audit_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build local MusicForge Release Portfolio Governance Audit reports and packages.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh and persist the Governance Audit report and ledger.")
    parser.add_argument("--ledger", action="store_true", help="Include ledger entries in output.")
    parser.add_argument("--ledger-limit", type=int, default=0, help="Limit output ledger entries to the last N rows.")
    parser.add_argument("--export", action="store_true", help="Build the Governance Audit export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Governance Audit ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Governance Audit ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat strict verifier warnings as failures.")
    parser.add_argument("--require-signed", action="store_true", help="When verifying, require every queue to be signed.")
    parser.add_argument("--require-archives", action="store_true", help="When verifying, require signed queues to have verified archives.")
    parser.add_argument("--require-no-force", action="store_true", help="When verifying, fail on force-signed governance evidence.")
    parser.add_argument("--require-reset-cr-causality", action="store_true", help="When verifying, require reset events to bind to applied Change Requests.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_governance_reviewer_pack_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Portfolio Governance Reviewer Packs.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Portfolio Governance Reviewer Report.")
    parser.add_argument("--export", action="store_true", help="Build the Portfolio Governance Reviewer Pack export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Portfolio Governance Reviewer Pack ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Portfolio Governance Reviewer Pack ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-audit", action="store_true", help="Require passed Governance Audit evidence when verifying.")
    parser.add_argument("--require-signed", action="store_true", help="Require every Governance Queue to be signed when verifying.")
    parser.add_argument("--require-archives", action="store_true", help="Require signed queues to have verified Governance Archives.")
    parser.add_argument("--require-no-force", action="store_true", help="Fail when force-signed governance evidence is present.")
    parser.add_argument("--require-reset-cr-causality", action="store_true", help="Require signoff reset events to be bound to applied Change Requests.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_governance_final_board_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build, sign, archive, and verify local MusicForge Release Portfolio Governance Final Board evidence.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Final Board Report.")
    parser.add_argument("--require-reviewer-response", action="store_true", help="Require an accepted external reviewer response.")
    parser.add_argument("--require-no-force", action="store_true", help="Treat force-signed governance evidence as blocking.")
    parser.add_argument("--import-reviewer-response", type=Path, default=None, help="Import an external reviewer response JSON file.")
    parser.add_argument("--sign", action="store_true", help="Sign the Final Board evidence.")
    parser.add_argument("--force-sign", action="store_true", help="Force sign when only warnings remain.")
    parser.add_argument("--allow-warning-signoff", action="store_true", help="Allow warning signoff without force.")
    parser.add_argument("--signed-by", default=None, help="Signer name for Final Board Signoff.")
    parser.add_argument("--role", default=None, help="Signer role.")
    parser.add_argument("--reason", default=None, help="Signoff/reset/change request reason.")
    parser.add_argument("--override-reason", default=None, help="Required for force signoff.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Final Board Change Request.")
    parser.add_argument("--approve-change-request", default=None, help="Approve a Final Board Change Request id.")
    parser.add_argument("--reject-change-request", default=None, help="Reject a Final Board Change Request id.")
    parser.add_argument("--change-request-id", default=None, help="Change Request id for reset.")
    parser.add_argument("--approved-by", default=None, help="Approver name for Change Request approval.")
    parser.add_argument("--reset-signoff", action="store_true", help="Reset Final Board Signoff using an approved Change Request.")
    parser.add_argument("--export", action="store_true", help="Build the Final Board Archive export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Final Board Archive ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Final Board Archive ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-signed", action="store_true", help="When verifying, require signed Final Board Signoff.")
    parser.add_argument("--require-reviewer-pack", action="store_true", help="When verifying, require Reviewer Pack evidence.")
    parser.add_argument("--require-audit", action="store_true", help="When verifying, require Governance Audit evidence.")
    parser.add_argument("--require-archives", action="store_true", help="When verifying, require verified Governance Archive coverage.")
    parser.add_argument("--require-reset-cr-causality", action="store_true", help="When verifying, require reset events to bind to applied Change Requests.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_governance_evidence_vault_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Portfolio Governance Evidence Vault packages.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Evidence Vault Report.")
    parser.add_argument("--export", action="store_true", help="Build the Evidence Vault export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Evidence Vault ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Evidence Vault ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--deep", action="store_true", help="Run nested package verifiers.")
    parser.add_argument("--require-final-board", action="store_true", help="Require passed Final Board Archive evidence.")
    parser.add_argument("--require-reviewer-pack", action="store_true", help="Require passed Governance Reviewer Pack evidence.")
    parser.add_argument("--require-audit", action="store_true", help="Require passed Governance Audit evidence.")
    parser.add_argument("--require-archives", action="store_true", help="Require signed queue Governance Archive evidence.")
    parser.add_argument("--require-queue-packages", action="store_true", help="Require Governance Queue ZIP evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_governance_attestation_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Portfolio Governance Public Attestation packages.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile: public_summary, partner_due_diligence, or internal_public_preview.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Public Attestation Report.")
    parser.add_argument("--export", action="store_true", help="Build the Public Attestation export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Public Attestation ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Public Attestation ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-vault", action="store_true", help="Require passed deep Evidence Vault verification.")
    parser.add_argument("--require-final-board", action="store_true", help="Require Final Board signoff evidence.")
    parser.add_argument("--require-no-force", action="store_true", help="Fail when force-signed governance evidence is present.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_governance_attestation_registry_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local MusicForge Release Portfolio Governance Public Attestation registries.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--register-current", action="store_true", help="Register the current verified Public Attestation ZIP.")
    parser.add_argument("--publish", metavar="ENTRY_ID", default=None, help="Publish a registry entry.")
    parser.add_argument("--supersede-current", action="store_true", help="Allow publish to supersede the current entry.")
    parser.add_argument("--revoke", metavar="ENTRY_ID", default=None, help="Revoke a published or superseded registry entry.")
    parser.add_argument("--reason", default="", help="Revocation reason.")
    parser.add_argument("--public-url", default="", help="Optional public URL for the published entry.")
    parser.add_argument("--distribution-note", default="", help="Optional public distribution note.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the registry report.")
    parser.add_argument("--export", action="store_true", help="Build the registry export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the registry ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the registry ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-current", action="store_true", help="Require a current published registry entry.")
    parser.add_argument("--require-published", action="store_true", help="Require at least one published registry entry.")
    parser.add_argument("--require-no-revoked-current", action="store_true", help="Fail when the current registry entry is revoked.")
    parser.add_argument("--require-accepted-evidence", action="store_true", help="Require current accepted external review evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_governance_attestation_portal_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Portfolio Governance Public Attestation Portal snapshots.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Attestation Portal Report.")
    parser.add_argument("--export", action="store_true", help="Build the Attestation Portal export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Attestation Portal ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Attestation Portal ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-current", action="store_true", help="Require a current published portal entry.")
    parser.add_argument("--require-registry", action="store_true", help="Require passed Attestation Registry evidence.")
    parser.add_argument("--require-attestation", action="store_true", help="Require passed Public Attestation evidence.")
    parser.add_argument("--require-accepted-evidence", action="store_true", help="Require current accepted external review evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_governance_attestation_portal_review_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build local MusicForge Public Attestation Portal review packs and import external responses.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--refresh-pack", action="store_true", help="Refresh the Portal Review Pack.")
    parser.add_argument("--export-pack", action="store_true", help="Build the Portal Review Pack export directory.")
    parser.add_argument("--zip-pack", action="store_true", help="Build the Portal Review Pack ZIP.")
    parser.add_argument("--verify-pack", action="store_true", help="Verify the Portal Review Pack ZIP.")
    parser.add_argument("--import-response", action="store_true", help="Import an external Portal Review Response from content_base64.")
    parser.add_argument("--content-base64", default="", help="Base64 JSON or ZIP response payload for --import-response.")
    parser.add_argument("--response-id", default="", help="Response id for detail, verify, or Change Request creation.")
    parser.add_argument("--responses", action="store_true", help="List imported responses.")
    parser.add_argument("--verify-response", action="store_true", help="Verify an imported response.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Change Request draft from a needs_changes/rejected response.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-current", action="store_true", help="Require current source evidence when verifying.")
    parser.add_argument("--require-pack", action="store_true", help="Require response to bind to a Review Pack source.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_governance_attestation_accepted_evidence_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local MusicForge Public Attestation Accepted Evidence packages.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--refresh", action="store_true", help="Refresh Accepted Evidence from an accepted Portal Review Response.")
    parser.add_argument("--response-id", default="", help="Accepted Portal Review Response id.")
    parser.add_argument("--export", action="store_true", help="Build the Accepted Evidence export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Accepted Evidence ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Accepted Evidence ZIP package.")
    parser.add_argument("--archive", action="store_true", help="Archive current Accepted Evidence.")
    parser.add_argument("--reason", default="", help="Archive reason.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-current", action="store_true", help="Require current accepted evidence when verifying.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_governance_attestation_transparency_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local MusicForge Public Attestation Transparency Feed packages.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Transparency Feed.")
    parser.add_argument("--export", action="store_true", help="Build the Transparency export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Transparency ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Transparency ZIP package.")
    parser.add_argument("--notices", action="store_true", help="List current change notices.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-current", action="store_true", help="Require a current published registry entry.")
    parser.add_argument("--require-accepted-evidence", action="store_true", help="Require current accepted external review evidence.")
    parser.add_argument("--require-no-revoked-current", action="store_true", help="Fail when the current registry entry is revoked.")
    parser.add_argument("--require-contiguous-chain", action="store_true", help="Require a valid contiguous transparency event chain.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_release_portfolio_governance_attestation_transparency_acknowledgement_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local MusicForge Public Attestation Transparency Acknowledgement packages.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--refresh-pack", action="store_true", help="Refresh the Transparency Acknowledgement Pack.")
    parser.add_argument("--export-pack", action="store_true", help="Build the Acknowledgement Pack export directory.")
    parser.add_argument("--zip-pack", action="store_true", help="Build the Acknowledgement Pack ZIP package.")
    parser.add_argument("--verify-pack", action="store_true", help="Verify the Acknowledgement Pack ZIP package.")
    parser.add_argument("--import-response", action="store_true", help="Import an uploaded acknowledgement response.")
    parser.add_argument("--content-base64", default="", help="Base64-encoded acknowledgement response JSON or ZIP.")
    parser.add_argument("--response-id", default="", help="Acknowledgement response id.")
    parser.add_argument("--refresh-evidence", action="store_true", help="Refresh accepted acknowledgement evidence.")
    parser.add_argument("--export-evidence", action="store_true", help="Build the Acknowledgement Evidence export directory.")
    parser.add_argument("--zip-evidence", action="store_true", help="Build the Acknowledgement Evidence ZIP package.")
    parser.add_argument("--verify-evidence", action="store_true", help="Verify the Acknowledgement Evidence ZIP package.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Change Request draft from a needs_changes/rejected response.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-pack", action="store_true", help="Require an Acknowledgement Pack package when verifying.")
    parser.add_argument("--require-response", action="store_true", help="Require Acknowledgement Evidence when verifying.")
    parser.add_argument("--require-accepted", action="store_true", help="Require accepted acknowledgement evidence when verifying.")
    parser.add_argument("--require-transparency", action="store_true", help="Require passed Transparency verification and semantics.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_verify_human_review_pack_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Human Review Pack ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Human Review Pack ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=512, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=2048, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_audit_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Audit ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Audit ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require every Governance Queue in the audit to be signed.")
    verify_parser.add_argument("--require-archives", action="store_true", help="Require signed queues to have verified Governance Archives.")
    verify_parser.add_argument("--require-no-force", action="store_true", help="Fail when force-signed governance evidence is present.")
    verify_parser.add_argument("--require-reset-cr-causality", action="store_true", help="Require signoff reset events to be bound to applied Change Requests.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_reviewer_pack_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Reviewer Pack ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Reviewer Pack ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-audit", action="store_true", help="Require passed Governance Audit evidence.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require every Governance Queue in the pack to be signed.")
    verify_parser.add_argument("--require-archives", action="store_true", help="Require signed queues to have verified Governance Archives.")
    verify_parser.add_argument("--require-no-force", action="store_true", help="Fail when force-signed governance evidence is present.")
    verify_parser.add_argument("--require-reset-cr-causality", action="store_true", help="Require signoff reset events to be bound to applied Change Requests.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_final_board_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Final Board Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Final Board Archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Final Board Signoff.")
    verify_parser.add_argument("--require-reviewer-pack", action="store_true", help="Require passed Governance Reviewer Pack evidence.")
    verify_parser.add_argument("--require-audit", action="store_true", help="Require passed Governance Audit evidence.")
    verify_parser.add_argument("--require-archives", action="store_true", help="Require verified Governance Archive coverage.")
    verify_parser.add_argument("--require-reviewer-response", action="store_true", help="Require accepted external reviewer response.")
    verify_parser.add_argument("--require-no-force", action="store_true", help="Fail when force-signed governance evidence is present.")
    verify_parser.add_argument("--require-reset-cr-causality", action="store_true", help="Require signoff reset events to be bound to applied Change Requests.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_evidence_vault_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Evidence Vault ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Evidence Vault ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--deep", action="store_true", help="Run nested package verifiers.")
    verify_parser.add_argument("--require-final-board", action="store_true", help="Require passed Final Board Archive evidence.")
    verify_parser.add_argument("--require-reviewer-pack", action="store_true", help="Require passed Governance Reviewer Pack evidence.")
    verify_parser.add_argument("--require-audit", action="store_true", help="Require passed Governance Audit evidence.")
    verify_parser.add_argument("--require-archives", action="store_true", help="Require signed queue Governance Archive evidence.")
    verify_parser.add_argument("--require-queue-packages", action="store_true", help="Require Governance Queue ZIP evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=1024, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=4096, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=20000, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_attestation_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Public Attestation ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Public Attestation ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-vault", action="store_true", help="Require passed deep Evidence Vault verification.")
    verify_parser.add_argument("--require-final-board", action="store_true", help="Require Final Board signoff evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_attestation_registry_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Public Attestation Registry ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Public Attestation Registry ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require a current published registry entry.")
    verify_parser.add_argument("--require-published", action="store_true", help="Require at least one published registry entry.")
    verify_parser.add_argument("--require-no-revoked-current", action="store_true", help="Fail when the current registry entry is revoked.")
    verify_parser.add_argument("--require-accepted-evidence", action="store_true", help="Require current accepted external review evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_attestation_portal_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Public Attestation Portal ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Public Attestation Portal ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require a current published portal entry.")
    verify_parser.add_argument("--require-registry", action="store_true", help="Require passed Attestation Registry evidence.")
    verify_parser.add_argument("--require-attestation", action="store_true", help="Require passed Public Attestation evidence.")
    verify_parser.add_argument("--require-accepted-evidence", action="store_true", help="Require current accepted external review evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_attestation_portal_review_pack_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Public Attestation Portal Review Pack ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Portal Review Pack ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current verified Portal evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_attestation_portal_response_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Public Attestation Portal Review Response ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Portal Review Response ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current response source evidence.")
    verify_parser.add_argument("--require-pack", action="store_true", help="Require response to bind to a Review Pack source.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_attestation_accepted_evidence_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Public Attestation Accepted Evidence ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Accepted Evidence ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current accepted external review evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_attestation_transparency_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Public Attestation Transparency ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Attestation Transparency ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require a current published registry entry.")
    verify_parser.add_argument("--require-accepted-evidence", action="store_true", help="Require current accepted external review evidence.")
    verify_parser.add_argument("--require-no-revoked-current", action="store_true", help="Fail when the current registry entry is revoked.")
    verify_parser.add_argument("--require-contiguous-chain", action="store_true", help="Require a valid contiguous transparency event chain.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=300, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_release_portfolio_governance_attestation_transparency_acknowledgement_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Public Attestation Transparency Acknowledgement ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Transparency Acknowledgement Pack/Evidence ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-pack", action="store_true", help="Require an Acknowledgement Pack package.")
    verify_parser.add_argument("--require-response", action="store_true", help="Require Acknowledgement Evidence.")
    verify_parser.add_argument("--require-accepted", action="store_true", help="Require accepted acknowledgement evidence.")
    verify_parser.add_argument("--require-transparency", action="store_true", help="Require passed Transparency verification and semantics.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=300, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_public_trust_center_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Public Trust Center ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Public Trust Center ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-release-readiness", action="store_true", help="Require selected releases to be ready.")
    verify_parser.add_argument("--require-public-attestation", action="store_true", help="Require registry, portal, and transparency evidence.")
    verify_parser.add_argument("--require-registry-current", action="store_true", help="Require current Registry evidence.")
    verify_parser.add_argument("--require-portal-current", action="store_true", help="Require current Portal evidence.")
    verify_parser.add_argument("--require-transparency-current", action="store_true", help="Require current Transparency evidence.")
    verify_parser.add_argument("--require-acknowledgement-current", action="store_true", help="Require current accepted acknowledgement evidence.")
    verify_parser.add_argument("--require-delivery-readiness", action="store_true", help="Require selected delivery chain rows to be ready.")
    verify_parser.add_argument("--require-distribution-ready", action="store_true", help="Require distribution evidence to be signed and verified.")
    verify_parser.add_argument("--require-submission-accepted", action="store_true", help="Require submission batches to be accepted.")
    verify_parser.add_argument("--require-submission-evidence", action="store_true", help="Require signed submission evidence packages.")
    verify_parser.add_argument("--require-operations-signed", action="store_true", help="Require Release Operations Signoff evidence.")
    verify_parser.add_argument("--require-operations-audit", action="store_true", help="Require verified Release Operations Audit evidence.")
    verify_parser.add_argument("--require-operations-reviewer-pack", action="store_true", help="Require verified Release Operations Reviewer Pack evidence.")
    verify_parser.add_argument("--require-acceptance-board-signoff", action="store_true", help="Require current Acceptance Board signoff archive evidence.")
    verify_parser.add_argument("--delivery-anchor", type=Path, default=None, help="Path to an external Public Trust Center delivery anchor JSON file.")
    verify_parser.add_argument("--anchor-registry", type=Path, default=None, help="Path to a Public Trust Center Anchor Registry ZIP.")
    verify_parser.add_argument("--anchor-transparency", type=Path, default=None, help="Path to a Public Trust Center Anchor Transparency ZIP.")
    verify_parser.add_argument("--anchor-checkpoint", type=Path, default=None, help="Path to an external Anchor Transparency checkpoint JSON.")
    verify_parser.add_argument("--acceptance-board-signoff-archive", type=Path, default=None, help="Path to an external Acceptance Board Signoff Archive ZIP.")
    verify_parser.add_argument("--acceptance-board", type=Path, default=None, help="Path to an external Acceptance Board ZIP.")
    verify_parser.add_argument("--acceptance-board-verification-report", type=Path, default=None, help="Path to the stored Acceptance Board verification report.")
    verify_parser.add_argument("--distribution-kit", type=Path, default=None, help="Path to an external Distribution Kit ZIP for signoff archive binding.")
    verify_parser.add_argument("--accepted-evidence-dir", type=Path, default=None, help="Directory containing Accepted Evidence ZIPs for signoff archive binding.")
    verify_parser.add_argument("--require-anchor-registry-current", action="store_true", help="Require the Anchor Registry current entry to match this package.")
    verify_parser.add_argument("--require-anchor-published", action="store_true", help="Require the Anchor Registry current entry to be published.")
    verify_parser.add_argument("--require-anchor-not-revoked", action="store_true", help="Require the Anchor Registry current entry not to be revoked.")
    verify_parser.add_argument("--require-anchor-transparency-current", action="store_true", help="Require Anchor Transparency evidence to match this package.")
    verify_parser.add_argument("--require-anchor-checkpoint", action="store_true", help="Require an external Anchor Transparency checkpoint.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=250, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_public_trust_center_anchor_registry_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Anchor Registry ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Anchor Registry ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require a current anchor entry.")
    verify_parser.add_argument("--require-anchor-published", action="store_true", help="Require the current anchor entry to be published.")
    verify_parser.add_argument("--require-anchor-not-revoked", action="store_true", help="Require the current anchor entry not to be revoked.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_public_trust_center_anchor_transparency_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Anchor Transparency ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Anchor Transparency ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--checkpoint", type=Path, default=None, help="External Anchor Transparency checkpoint JSON.")
    verify_parser.add_argument("--anchor-registry", type=Path, default=None, help="External Anchor Registry ZIP.")
    verify_parser.add_argument("--require-current-checkpoint", action="store_true", help="Require a current checkpoint.")
    verify_parser.add_argument("--require-published-anchor", action="store_true", help="Require the checkpoint current anchor to be published.")
    verify_parser.add_argument("--require-not-revoked", action="store_true", help="Require the checkpoint current anchor not to be revoked.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=250, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_public_trust_center_distribution_kit_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Distribution Kit ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Distribution Kit ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--deep", action="store_true", help="Re-run nested Public Trust Center, Anchor Registry, and Anchor Transparency verification.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current nested evidence.")
    verify_parser.add_argument("--require-delivery-readiness", dest="require_delivery_readiness", action="store_true", default=True, help="Require delivery readiness in nested PTC verification.")
    verify_parser.add_argument("--no-require-delivery-readiness", dest="require_delivery_readiness", action="store_false", help="Do not require delivery readiness in nested PTC verification.")
    verify_parser.add_argument("--require-anchor-registry-current", action="store_true", default=True, help="Require current Anchor Registry evidence.")
    verify_parser.add_argument("--require-anchor-published", action="store_true", default=True, help="Require published current anchor.")
    verify_parser.add_argument("--require-anchor-not-revoked", action="store_true", default=True, help="Require current anchor not revoked.")
    verify_parser.add_argument("--require-anchor-transparency-current", action="store_true", default=True, help="Require current Anchor Transparency evidence.")
    verify_parser.add_argument("--require-anchor-checkpoint", action="store_true", default=True, help="Require the included checkpoint.")
    verify_parser.add_argument("--require-acceptance-board-signoff", action="store_true", help="Require current Acceptance Board signoff archive evidence.")
    verify_parser.add_argument("--acceptance-board-signoff-archive", type=Path, default=None, help="Path to an external Acceptance Board Signoff Archive ZIP.")
    verify_parser.add_argument("--acceptance-board", type=Path, default=None, help="Path to an external Acceptance Board ZIP.")
    verify_parser.add_argument("--acceptance-board-verification-report", type=Path, default=None, help="Path to the stored Acceptance Board verification report.")
    verify_parser.add_argument("--accepted-evidence-dir", type=Path, default=None, help="Directory containing Accepted Evidence ZIPs for signoff archive binding.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=256, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=400, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_public_trust_center_distribution_kit_accepted_evidence_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Distribution Kit Accepted Evidence ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Accepted Evidence ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require the external Distribution Kit ZIP to match the evidence binding.")
    verify_parser.add_argument("--distribution-kit", type=Path, default=None, help="External Distribution Kit ZIP for current binding checks.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_public_trust_center_acceptance_board_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Acceptance Board ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Acceptance Board ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict warnings as failures.")
    verify_parser.add_argument("--require-ready", action="store_true", help="Require the board to be ready.")
    verify_parser.add_argument("--require-quorum", action="store_true", help="Require the board quorum gate to pass.")
    verify_parser.add_argument("--require-no-conflicts", action="store_true", help="Require no blocking board conflicts.")
    verify_parser.add_argument("--min-accepted-count", type=int, default=0, help="Minimum accepted evidence count required by the verifier.")
    verify_parser.add_argument("--min-accepted-organizations", type=int, default=0, help="Minimum accepted organization count required by the verifier.")
    verify_parser.add_argument("--required-role", action="append", dest="required_roles", default=[], help="Required reviewer role. Can be repeated.")
    verify_parser.add_argument("--distribution-kit", type=Path, default=None, help="External Distribution Kit ZIP for binding checks.")
    verify_parser.add_argument("--accepted-evidence-dir", type=Path, default=None, help="Directory containing Accepted Evidence ZIPs for future deep checks.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=160, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_public_trust_center_acceptance_board_signoff_archive_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Acceptance Board Signoff Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Acceptance Board Signoff Archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict warnings as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require a signed Acceptance Board signoff.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require external current board/evidence bindings.")
    verify_parser.add_argument("--require-ready", action="store_true", help="Require a ready and verified board.")
    verify_parser.add_argument("--board-zip", type=Path, default=None, help="External Acceptance Board ZIP for current checks.")
    verify_parser.add_argument("--board-verification-report", type=Path, default=None, help="Stored Acceptance Board verification report.")
    verify_parser.add_argument("--distribution-kit", type=Path, default=None, help="External Distribution Kit ZIP for binding checks.")
    verify_parser.add_argument("--accepted-evidence-dir", type=Path, default=None, help="Directory containing Accepted Evidence ZIPs.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_public_trust_center_publication_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Publication ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Publication ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict warnings as failures.")
    verify_parser.add_argument("--deep", action="store_true", help="Re-run nested package verifiers.")
    verify_parser.add_argument("--require-ready", action="store_true", help="Require publication ready status.")
    verify_parser.add_argument("--require-acceptance-board-signoff", action="store_true", help="Require Acceptance Board signoff evidence.")
    verify_parser.add_argument("--require-anchor-current", action="store_true", help="Require current Anchor Registry and Transparency evidence.")
    verify_parser.add_argument("--require-no-revoked", action="store_true", help="Fail revoked publication snapshots.")
    verify_parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json used for revoke/supersede checks.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=512, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=2048, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=512, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_public_trust_center_publication_mirror_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Publication mirror directory.")
    verify_parser.add_argument("mirror_dir", type=Path, help="Path to the Publication mirror directory to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict warnings as failures.")
    verify_parser.add_argument("--require-ready", action="store_true", help="Require publication ready status.")
    verify_parser.add_argument("--require-acceptance-board-signoff", action="store_true", help="Require Acceptance Board signoff evidence.")
    verify_parser.add_argument("--require-anchor-current", action="store_true", help="Require current Anchor Registry and Anchor Transparency evidence.")
    verify_parser.add_argument("--require-no-revoked", action="store_true", help="Fail if the publication snapshot is revoked.")
    verify_parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json used for revoke/supersede checks.")
    verify_parser.add_argument("--max-entry-count", type=int, default=512, help="Maximum number of mirror files.")
    return verify_parser


def build_verify_public_trust_center_publication_monitoring_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Publication Monitoring ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Publication Monitoring ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require the monitoring run to match current external channel state.")
    verify_parser.add_argument("--require-no-revoked", action="store_true", help="Fail revoked or superseded monitored publications.")
    verify_parser.add_argument("--require-ready", action="store_true", help="Require a passed monitoring run and publication verification.")
    verify_parser.add_argument("--require-no-drift", action="store_true", help="Require no critical/high drift.")
    verify_parser.add_argument("--require-no-open-critical-incidents", action="store_true", help="Require no open critical incident.")
    verify_parser.add_argument("--allow-waived-incidents", action="store_true", help="Allow waived high/critical incidents as warnings.")
    verify_parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json used for current/revoke checks.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=256, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_trust_operations_hub_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Hub ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Hub ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-ready", action="store_true", help="Require Hub readiness to be ready.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require Hub signoff summary.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current external source evidence.")
    verify_parser.add_argument("--require-no-critical-blockers", action="store_true", help="Require no critical blockers.")
    verify_parser.add_argument("--require-publication-monitoring-clean", action="store_true", help="Require clean publication monitoring evidence.")
    verify_parser.add_argument("--require-delivery-ready", action="store_true", help="Require full delivery-chain verification evidence.")
    verify_parser.add_argument("--require-incident-closeout", action="store_true", help="Require external Trust Operations Incident closeout evidence.")
    verify_parser.add_argument("--require-incident-regression-guards", action="store_true", help="Require external Trust Operations Incident Knowledge regression guard evidence.")
    verify_parser.add_argument("--require-trust-controls", action="store_true", help="Require Trust Operations Control Catalog policy evidence.")
    verify_parser.add_argument("--require-trust-control-signoff", action="store_true", help="Require Trust Operations Control Signoff archive evidence.")
    verify_parser.add_argument("--require-continuous-assurance", action="store_true", help="Require Trust Operations Continuous Assurance evidence.")
    verify_parser.add_argument("--require-assurance-watch-clear", action="store_true", help="Require Trust Operations Assurance Watch queue to be clear.")
    verify_parser.add_argument("--require-assurance-watch-signoff", action="store_true", help="Require Trust Operations Assurance Watch Signoff archive evidence.")
    verify_parser.add_argument("--require-final-readiness", action="store_true", help="Require Trust Operations Final Readiness handoff evidence.")
    verify_parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json used for current/revoke checks.")
    verify_parser.add_argument("--public-trust-center-verification", type=Path, default=None, help="External Public Trust Center verification report.")
    verify_parser.add_argument("--publication-monitoring-verification", type=Path, default=None, help="External Publication Monitoring verification report.")
    verify_parser.add_argument("--release-verification", type=Path, action="append", default=[], help="External Release ZIP verification report. Can be repeated.")
    verify_parser.add_argument("--distribution-verification", type=Path, action="append", default=[], help="External Distribution package verification report. Can be repeated.")
    verify_parser.add_argument("--submission-verification", type=Path, action="append", default=[], help="External Submission package verification report. Can be repeated.")
    verify_parser.add_argument("--submission-evidence-verification", type=Path, action="append", default=[], help="External Submission Evidence verification report. Can be repeated.")
    verify_parser.add_argument("--release-operations-verification", type=Path, action="append", default=[], help="External Release Operations verification report. Can be repeated.")
    verify_parser.add_argument("--hub-signoff", type=Path, default=None, help="External Trust Operations Hub signoff sidecar JSON.")
    verify_parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report used for signoff.")
    verify_parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    verify_parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    verify_parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    verify_parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    verify_parser.add_argument("--trust-control-package", type=Path, default=None, help="External Trust Operations Control ZIP.")
    verify_parser.add_argument("--trust-control-verification-report", type=Path, default=None, help="External Trust Operations Control verification report.")
    verify_parser.add_argument("--trust-control-signoff-archive", type=Path, default=None, help="External Trust Operations Control Signoff Archive ZIP.")
    verify_parser.add_argument("--trust-control-signoff-verification-report", type=Path, default=None, help="External Trust Operations Control Signoff verification report.")
    verify_parser.add_argument("--continuous-assurance-archive", type=Path, default=None, help="External Trust Operations Continuous Assurance Archive ZIP.")
    verify_parser.add_argument("--continuous-assurance-verification-report", type=Path, default=None, help="External Trust Operations Continuous Assurance verification report.")
    verify_parser.add_argument("--assurance-watch-package", type=Path, default=None, help="External Trust Operations Assurance Watch ZIP.")
    verify_parser.add_argument("--assurance-watch-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch verification report.")
    verify_parser.add_argument("--assurance-watch-signoff-archive", type=Path, default=None, help="External Trust Operations Assurance Watch Signoff Archive ZIP.")
    verify_parser.add_argument("--assurance-watch-signoff-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch Signoff verification report.")
    verify_parser.add_argument("--final-handoff-package", type=Path, default=None, help="External Trust Operations Final Handoff ZIP.")
    verify_parser.add_argument("--final-handoff-verification-report", type=Path, default=None, help="External Trust Operations Final Handoff verification report.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=256, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_trust_operations_assurance_watch_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Assurance Watch ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Assurance Watch ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-clear", action="store_true", help="Require the Watch queue to be clear.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current external Assurance and Hub evidence.")
    _add_trust_operations_assurance_watch_source_args(verify_parser)
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_trust_operations_assurance_watch_signoff_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Assurance Watch Signoff Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Assurance Watch Signoff archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Assurance Watch Signoff evidence.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current external Watch/Hub/Assurance evidence.")
    verify_parser.add_argument("--watch-package", type=Path, default=None, help="External Trust Operations Assurance Watch ZIP.")
    verify_parser.add_argument("--watch-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch verification report.")
    verify_parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    verify_parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    verify_parser.add_argument("--continuous-assurance-report", type=Path, default=None, help="External Trust Operations Continuous Assurance verification report.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_trust_operations_final_handoff_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Final Handoff ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Final Handoff ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Final Handoff evidence.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current external source evidence.")
    _add_trust_operations_final_readiness_source_args(verify_parser)
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=256, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=96, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_trust_operations_assurance_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Continuous Assurance Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Assurance archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-passed", action="store_true", help="Require Assurance status to be passed.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current external source evidence.")
    _add_trust_operations_assurance_source_args(verify_parser)
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_trust_operations_hub_runbook_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Hub Runbook ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Hub Runbook ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-completed", action="store_true", help="Require safe runbook actions to have run.")
    verify_parser.add_argument("--require-no-blocked", action="store_true", help="Require no blocked safe action results.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_trust_operations_hub_incident_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Incident Board ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Incident Board ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-no-open-critical", action="store_true", help="Require no open critical incidents.")
    verify_parser.add_argument("--require-no-open-blocking", action="store_true", help="Require no open blocking incidents.")
    verify_parser.add_argument("--require-current-hub", action="store_true", help="Require external current Hub verification evidence.")
    verify_parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_trust_operations_incident_knowledge_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Incident Knowledge ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Incident Knowledge ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-guards-passed", action="store_true", help="Require regression guards to have passed runs.")
    verify_parser.add_argument("--require-no-open-recurrence", action="store_true", help="Require no open incident recurrence.")
    verify_parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    verify_parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    verify_parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_trust_operations_control_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Control ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Control ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-policy-passed", action="store_true", help="Require the control policy assessment to pass.")
    verify_parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    verify_parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    verify_parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    verify_parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    verify_parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    verify_parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser


def build_verify_trust_operations_control_signoff_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Control Signoff Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Control Signoff archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Control Signoff evidence.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current external Control/Hub/Incident/Knowledge evidence.")
    verify_parser.add_argument("--control-package", type=Path, default=None, help="External Trust Operations Control ZIP.")
    verify_parser.add_argument("--control-verification-report", type=Path, default=None, help="External Trust Operations Control verification report.")
    verify_parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    verify_parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    verify_parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    verify_parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    verify_parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    verify_parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser


def _add_trust_operations_assurance_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    parser.add_argument("--control-signoff-archive", type=Path, default=None, help="External Trust Operations Control Signoff Archive ZIP.")
    parser.add_argument("--control-signoff-verification-report", type=Path, default=None, help="External Trust Operations Control Signoff verification report.")
    parser.add_argument("--control-package", type=Path, default=None, help="External Trust Operations Control ZIP.")
    parser.add_argument("--control-verification-report", type=Path, default=None, help="External Trust Operations Control verification report.")
    parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    parser.add_argument("--release-verification", type=Path, action="append", default=[], help="External Release ZIP verification report. Can be repeated.")
    parser.add_argument("--distribution-verification", type=Path, action="append", default=[], help="External Distribution package verification report. Can be repeated.")
    parser.add_argument("--submission-verification", type=Path, action="append", default=[], help="External Submission package verification report. Can be repeated.")
    parser.add_argument("--submission-evidence-verification", type=Path, action="append", default=[], help="External Submission Evidence verification report. Can be repeated.")
    parser.add_argument("--release-operations-verification", type=Path, action="append", default=[], help="External Release Operations verification report. Can be repeated.")


def build_public_trust_center_publication_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify MusicForge Public Trust Center Publication channels.")
    parser.add_argument("--center-id", default="ptc-default", help="Public Trust Center id.")
    parser.add_argument("--channel-id", default="public-release", help="Publication channel id.")
    parser.add_argument("--channel-name", default="Public Release Channel", help="Publication channel name.")
    parser.add_argument("--channel-type", default="public_release", help="Publication channel type.")
    parser.add_argument("--create-channel", action="store_true", help="Create the publication channel if needed.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the current publication report.")
    parser.add_argument("--export", action="store_true", help="Export the publication mirror directory.")
    parser.add_argument("--zip", action="store_true", help="Build the publication ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the publication ZIP.")
    parser.add_argument("--verify-mirror", action="store_true", help="Verify the publication mirror directory.")
    parser.add_argument("--mirror-dir", type=Path, default=None, help="External mirror directory to verify. Defaults to current export.")
    parser.add_argument("--publication-id", default=None, help="Publication id. Defaults to the current publication.")
    parser.add_argument("--revoke", action="store_true", help="Revoke the publication snapshot.")
    parser.add_argument("--supersede", action="store_true", help="Create a new publication and mark the previous current one superseded.")
    parser.add_argument("--reason", default="Public Trust Center publication operation.", help="Reason for revoke/supersede operations.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--deep", action="store_true", help="Run nested package verification.")
    parser.add_argument("--require-ready", action="store_true", default=True, help="Verifier requires ready publication state.")
    parser.add_argument("--no-require-ready", dest="require_ready", action="store_false", help="Do not require ready publication state.")
    parser.add_argument("--require-acceptance-board-signoff", action="store_true", default=True, help="Verifier requires Acceptance Board signoff.")
    parser.add_argument("--no-require-acceptance-board-signoff", dest="require_acceptance_board_signoff", action="store_false", help="Do not require Acceptance Board signoff.")
    parser.add_argument("--require-anchor-current", action="store_true", default=True, help="Verifier requires current anchor evidence.")
    parser.add_argument("--no-require-anchor-current", dest="require_anchor_current", action="store_false", help="Do not require current anchor evidence.")
    parser.add_argument("--require-no-revoked", action="store_true", help="Verifier fails revoked snapshots.")
    parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json used for revoke/supersede checks.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_public_trust_center_publication_monitor_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run and export MusicForge Public Trust Center Publication monitoring.")
    parser.add_argument("--center-id", default="ptc-default", help="Public Trust Center id.")
    parser.add_argument("--channel-id", default="public-release", help="Publication channel id.")
    parser.add_argument("--monitor-id", default=None, help="Publication monitor id.")
    parser.add_argument("--run-id", default=None, help="Monitoring run id.")
    parser.add_argument("--create-monitor", action="store_true", help="Create a monitor if needed.")
    parser.add_argument("--monitor-name", default="Public Release Monitor", help="Monitor display name.")
    parser.add_argument("--publication-id", default=None, help="Publication id, or current.")
    parser.add_argument("--mirror-dir", type=Path, default=None, help="Mirror directory to monitor. Defaults to publication export dir.")
    parser.add_argument("--run", action="store_true", help="Run the monitor.")
    parser.add_argument("--export", action="store_true", help="Export the monitoring package directory.")
    parser.add_argument("--zip", action="store_true", help="Build the monitoring ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the monitoring ZIP.")
    parser.add_argument("--ack-incident", default=None, help="Acknowledge an incident id.")
    parser.add_argument("--resolve-incident", default=None, help="Resolve an incident id.")
    parser.add_argument("--waive-incident", default=None, help="Waive an incident id.")
    parser.add_argument("--reopen-incident", default=None, help="Reopen an incident id.")
    parser.add_argument("--reason", default="Publication monitoring operation.", help="Reason for incident transitions.")
    parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json used for current/revoke checks.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-current", action="store_true", help="Verifier requires current external channel state.")
    parser.add_argument("--require-no-revoked", action="store_true", help="Verifier fails revoked/superseded monitored publications.")
    parser.add_argument("--require-ready", action="store_true", help="Verifier requires a passed monitoring run.")
    parser.add_argument("--require-no-drift", action="store_true", help="Verifier requires no critical/high drift.")
    parser.add_argument("--require-no-open-critical-incidents", action="store_true", help="Verifier requires no open critical incident.")
    parser.add_argument("--allow-waived-incidents", action="store_true", help="Allow waived high/critical incidents as warnings.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_trust_operations_hub_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build, sign, and verify MusicForge Trust Operations Hub packages.")
    parser.add_argument("--hub-id", default=None, help="Trust Operations Hub id.")
    parser.add_argument("--name", default="Default Trust Operations Hub", help="Hub display name.")
    parser.add_argument("--create", action="store_true", help="Create the Hub if it does not exist.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Hub report.")
    parser.add_argument("--report-id", default=None, help="Hub report id. Defaults to current report when possible.")
    parser.add_argument("--export", action="store_true", help="Export the Hub package directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Hub ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Hub ZIP.")
    parser.add_argument("--signoff", action="store_true", help="Sign off the verified Hub ZIP.")
    parser.add_argument("--signed-by", default="local-reviewer", help="Signer name for Hub signoff.")
    parser.add_argument("--reason", default="Trust Operations Hub operation.", help="Reason for signoff/change request/reset.")
    parser.add_argument("--force", action="store_true", help="Force signoff when allowed.")
    parser.add_argument("--override-reason", default="", help="Required reason for forced signoff.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Hub change request.")
    parser.add_argument("--approve-change-request", default=None, help="Approve a Hub change request id.")
    parser.add_argument("--reset-signoff", action="store_true", help="Reset Hub signoff with an approved change request.")
    parser.add_argument("--change-request-id", default=None, help="Change request id for reset.")
    parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json.")
    parser.add_argument("--public-trust-center-verification", type=Path, default=None, help="External Public Trust Center verification report.")
    parser.add_argument("--publication-monitoring-verification", type=Path, default=None, help="External Publication Monitoring verification report.")
    parser.add_argument("--release-verification", type=Path, action="append", default=[], help="External Release ZIP verification report. Can be repeated.")
    parser.add_argument("--distribution-verification", type=Path, action="append", default=[], help="External Distribution package verification report. Can be repeated.")
    parser.add_argument("--submission-verification", type=Path, action="append", default=[], help="External Submission package verification report. Can be repeated.")
    parser.add_argument("--submission-evidence-verification", type=Path, action="append", default=[], help="External Submission Evidence verification report. Can be repeated.")
    parser.add_argument("--release-operations-verification", type=Path, action="append", default=[], help="External Release Operations verification report. Can be repeated.")
    parser.add_argument("--hub-signoff", type=Path, default=None, help="External Trust Operations Hub signoff sidecar JSON.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report used for signoff.")
    parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-ready", action="store_true", help="Verifier requires ready Hub.")
    parser.add_argument("--require-signed", action="store_true", help="Verifier requires Hub signoff summary.")
    parser.add_argument("--require-current", action="store_true", help="Verifier requires current external source evidence.")
    parser.add_argument("--require-no-critical-blockers", action="store_true", help="Verifier requires no critical blockers.")
    parser.add_argument("--require-publication-monitoring-clean", action="store_true", help="Verifier requires clean publication monitoring evidence.")
    parser.add_argument("--require-delivery-ready", action="store_true", help="Verifier requires full delivery-chain verification evidence.")
    parser.add_argument("--require-incident-closeout", action="store_true", help="Verifier requires Trust Operations Incident closeout evidence.")
    parser.add_argument("--require-incident-regression-guards", action="store_true", help="Verifier requires Trust Operations Incident Knowledge regression guard evidence.")
    parser.add_argument("--require-trust-controls", action="store_true", help="Verifier requires Trust Operations Control policy evidence.")
    parser.add_argument("--trust-control-package", type=Path, default=None, help="External Trust Operations Control ZIP.")
    parser.add_argument("--trust-control-verification-report", type=Path, default=None, help="External Trust Operations Control verification report.")
    parser.add_argument("--require-trust-control-signoff", action="store_true", help="Verifier requires Trust Operations Control Signoff archive evidence.")
    parser.add_argument("--trust-control-signoff-archive", type=Path, default=None, help="External Trust Operations Control Signoff Archive ZIP.")
    parser.add_argument("--trust-control-signoff-verification-report", type=Path, default=None, help="External Trust Operations Control Signoff verification report.")
    parser.add_argument("--require-continuous-assurance", action="store_true", help="Verifier requires Trust Operations Continuous Assurance evidence.")
    parser.add_argument("--continuous-assurance-archive", type=Path, default=None, help="External Trust Operations Continuous Assurance Archive ZIP.")
    parser.add_argument("--continuous-assurance-verification-report", type=Path, default=None, help="External Trust Operations Continuous Assurance verification report.")
    parser.add_argument("--require-assurance-watch-clear", action="store_true", help="Verifier requires Trust Operations Assurance Watch clear evidence.")
    parser.add_argument("--assurance-watch-package", type=Path, default=None, help="External Trust Operations Assurance Watch ZIP.")
    parser.add_argument("--assurance-watch-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch verification report.")
    parser.add_argument("--require-assurance-watch-signoff", action="store_true", help="Verifier requires Trust Operations Assurance Watch Signoff archive evidence.")
    parser.add_argument("--assurance-watch-signoff-archive", type=Path, default=None, help="External Trust Operations Assurance Watch Signoff Archive ZIP.")
    parser.add_argument("--assurance-watch-signoff-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch Signoff verification report.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_trust_operations_assurance_watch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify Trust Operations Assurance Watch queues.")
    parser.add_argument("--schedule-id", default="default", help="Assurance Watch schedule id.")
    parser.add_argument("--queue-id", default=None, help="Assurance Watch queue id.")
    parser.add_argument("--hub-id", default=None, help="Trust Operations Hub id.")
    parser.add_argument("--write-schedule", action="store_true", help="Create or update the Assurance Watch schedule.")
    parser.add_argument("--interval-days", type=int, default=None, help="Schedule interval in days.")
    parser.add_argument("--grace-days", type=int, default=None, help="Schedule grace window in days.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Watch queue.")
    parser.add_argument("--list", action="store_true", help="List Watch queues.")
    parser.add_argument("--export", action="store_true", help="Export the Watch archive directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Watch ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Watch ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-clear", action="store_true", default=True, help="Verifier requires the Watch queue to be clear.")
    parser.add_argument("--no-require-clear", dest="require_clear", action="store_false", help="Do not require the Watch queue to be clear.")
    parser.add_argument("--require-current", action="store_true", default=True, help="Verifier requires current external evidence.")
    parser.add_argument("--no-require-current", dest="require_current", action="store_false", help="Do not require current external evidence.")
    _add_trust_operations_assurance_watch_source_args(parser)
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_trust_operations_assurance_watch_signoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sign, archive, and verify Trust Operations Assurance Watch closeout evidence.")
    parser.add_argument("--queue-id", required=True, help="Assurance Watch queue id.")
    parser.add_argument("--refresh-closeout", action="store_true", help="Refresh the Assurance Watch closeout.")
    parser.add_argument("--sign", action="store_true", help="Sign the current passed closeout.")
    parser.add_argument("--signed-by", default="local-reviewer", help="Signer name.")
    parser.add_argument("--role", default="owner", help="Signer role.")
    parser.add_argument("--reason", default="Assurance Watch queue clear and verified.", help="Signoff/change request reason.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a signoff reset change request.")
    parser.add_argument("--approve-change-request", default=None, help="Approve a change request id.")
    parser.add_argument("--reset-signoff", default=None, help="Reset signoff with an approved change request id.")
    parser.add_argument("--export", action="store_true", help="Export the signoff archive directory.")
    parser.add_argument("--zip", action="store_true", help="Build the signoff archive ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the signoff archive ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-signed", action="store_true", default=True, help="Verifier requires signed evidence.")
    parser.add_argument("--no-require-signed", dest="require_signed", action="store_false", help="Do not require signed evidence.")
    parser.add_argument("--require-current", action="store_true", default=True, help="Verifier requires current external evidence.")
    parser.add_argument("--no-require-current", dest="require_current", action="store_false", help="Do not require current external evidence.")
    parser.add_argument("--watch-package", type=Path, default=None, help="External Trust Operations Assurance Watch ZIP.")
    parser.add_argument("--watch-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch verification report.")
    parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    parser.add_argument("--continuous-assurance-report", type=Path, default=None, help="External Trust Operations Continuous Assurance verification report.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_trust_operations_final_readiness_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, sign, archive, and verify Trust Operations Final Readiness handoff evidence.")
    parser.add_argument("--refresh-report", action="store_true", help="Refresh the Final Readiness report.")
    parser.add_argument("--create-certificate", action="store_true", help="Create the Final Readiness certificate.")
    parser.add_argument("--sign", action="store_true", help="Sign the Final Handoff.")
    parser.add_argument("--signed-by", default="local-reviewer", help="Signer name.")
    parser.add_argument("--role", default="owner", help="Signer role.")
    parser.add_argument("--reason", default="Trust Operations final readiness accepted.", help="Signoff/change request reason.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Final Handoff reset change request.")
    parser.add_argument("--approve-change-request", default=None, help="Approve a change request id.")
    parser.add_argument("--reset-signoff", default=None, help="Reset Final Handoff with an approved change request id.")
    parser.add_argument("--export", action="store_true", help="Export the Final Handoff directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Final Handoff ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Final Handoff ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-signed", action="store_true", default=True, help="Verifier requires signed evidence.")
    parser.add_argument("--no-require-signed", dest="require_signed", action="store_false", help="Do not require signed evidence.")
    parser.add_argument("--require-current", action="store_true", default=True, help="Verifier requires current external evidence.")
    parser.add_argument("--no-require-current", dest="require_current", action="store_false", help="Do not require current external evidence.")
    _add_trust_operations_final_readiness_source_args(parser)
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_trust_operations_assurance_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify Trust Operations Continuous Assurance archives.")
    parser.add_argument("--hub-id", default="hub", help="Trust Operations Hub id.")
    parser.add_argument("--run-id", default=None, help="Assurance run id.")
    parser.add_argument("--policy-id", default="default", help="Assurance policy id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh and persist an Assurance run.")
    parser.add_argument("--list", action="store_true", help="List Assurance runs.")
    parser.add_argument("--export", action="store_true", help="Export the Assurance archive directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Assurance ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Assurance ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-passed", action="store_true", default=True, help="Verifier requires passed Assurance.")
    parser.add_argument("--no-require-passed", dest="require_passed", action="store_false", help="Do not require passed Assurance.")
    parser.add_argument("--require-current", action="store_true", default=True, help="Verifier requires current external evidence.")
    parser.add_argument("--no-require-current", dest="require_current", action="store_false", help="Do not require current external evidence.")
    _add_trust_operations_assurance_source_args(parser)
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_trust_operations_control_signoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sign, archive, and verify Trust Operations Controls.")
    parser.add_argument("--hub-id", default="hub", help="Trust Operations Hub id.")
    parser.add_argument("--assessment-id", default=None, help="Control assessment id.")
    parser.add_argument("--sign", action="store_true", help="Sign the current Control verification evidence.")
    parser.add_argument("--signed-by", default="local-reviewer", help="Signer name.")
    parser.add_argument("--reason", default="Trust Operations control signoff operation.", help="Reason for signoff/change request/exception.")
    parser.add_argument("--request-exception", action="store_true", help="Request a Control exception.")
    parser.add_argument("--approve-exception", action="store_true", help="Approve a Control exception.")
    parser.add_argument("--reject-exception", action="store_true", help="Reject a Control exception.")
    parser.add_argument("--exception-id", default=None, help="Control exception id.")
    parser.add_argument("--control-id", default=None, help="Control id for an exception.")
    parser.add_argument("--requested-by", default="local-operator", help="Exception requester.")
    parser.add_argument("--approved-by", default="local-reviewer", help="Exception or CR approver.")
    parser.add_argument("--expires-at", default=None, help="Exception expiry timestamp.")
    parser.add_argument("--mitigation", default="", help="Exception mitigation note.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Control Signoff change request.")
    parser.add_argument("--approve-change-request", action="store_true", help="Approve a Control Signoff change request.")
    parser.add_argument("--change-request-id", default=None, help="Change request id.")
    parser.add_argument("--reset", action="store_true", help="Reset Control Signoff with an approved change request.")
    parser.add_argument("--export", action="store_true", help="Export the Control Signoff archive directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Control Signoff archive ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Control Signoff archive ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-signed", action="store_true", default=True, help="Verifier requires signed evidence.")
    parser.add_argument("--no-require-signed", dest="require_signed", action="store_false", help="Do not require signed evidence.")
    parser.add_argument("--require-current", action="store_true", default=True, help="Verifier requires current external evidence.")
    parser.add_argument("--no-require-current", dest="require_current", action="store_false", help="Do not require current external evidence.")
    parser.add_argument("--control-package", type=Path, default=None, help="External Trust Operations Control ZIP.")
    parser.add_argument("--control-verification-report", type=Path, default=None, help="External Trust Operations Control verification report.")
    parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_trust_operations_hub_runbook_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, run, export, and verify Trust Operations Hub Runbooks.")
    parser.add_argument("--hub-id", default="hub", help="Trust Operations Hub id.")
    parser.add_argument("--report-id", default=None, help="Hub report id. Defaults to current report when possible.")
    parser.add_argument("--runbook-id", default=None, help="Runbook id. Defaults to current or new runbook.")
    parser.add_argument("--create", action="store_true", help="Create a runbook from the current Hub report.")
    parser.add_argument("--run-safe", action="store_true", help="Run only safe automated actions.")
    parser.add_argument("--export", action="store_true", help="Export the runbook package directory.")
    parser.add_argument("--zip", action="store_true", help="Build the runbook ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the runbook ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-completed", action="store_true", help="Verifier requires completed runbook results.")
    parser.add_argument("--require-no-blocked", action="store_true", help="Verifier requires no blocked safe action results.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_trust_operations_hub_incidents_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, remediate, export, and verify Trust Operations Incidents.")
    parser.add_argument("--hub-id", default="hub", help="Trust Operations Hub id.")
    parser.add_argument("--report-id", default=None, help="Hub report id. Defaults to current report.")
    parser.add_argument("--incident-id", default=None, help="Incident id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh Incident Board from Hub blockers.")
    parser.add_argument("--list", action="store_true", help="List incidents.")
    parser.add_argument("--triage", action="store_true", help="Triage an incident.")
    parser.add_argument("--severity", default=None, help="Incident severity.")
    parser.add_argument("--owner", default="local-user", help="Triage owner.")
    parser.add_argument("--notes", default="", help="Triage notes.")
    parser.add_argument("--create-plan", action="store_true", help="Create a remediation plan.")
    parser.add_argument("--add-evidence", action="store_true", help="Add JSON verification evidence.")
    parser.add_argument("--evidence-kind", default="external_verification_report", help="Evidence kind.")
    parser.add_argument("--component-type", default=None, help="Evidence component type.")
    parser.add_argument("--component-id", default=None, help="Evidence component id.")
    parser.add_argument("--content-base64", default=None, help="Base64 encoded evidence JSON.")
    parser.add_argument("--evidence-file", type=Path, default=None, help="Evidence JSON file to read and import.")
    parser.add_argument("--verify-fix", action="store_true", help="Verify incident fix evidence.")
    parser.add_argument("--close", action="store_true", help="Close an incident.")
    parser.add_argument("--closed-by", default="local-user", help="Closeout actor.")
    parser.add_argument("--reason", default="Trust Operations incident remediated.", help="Closeout reason.")
    parser.add_argument("--archive", action="store_true", help="Archive a closed incident.")
    parser.add_argument("--export", action="store_true", help="Export the Incident Board package directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Incident Board ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Incident Board ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-no-open-critical", action="store_true", help="Verifier requires no open critical incidents.")
    parser.add_argument("--require-no-open-blocking", action="store_true", help="Verifier requires no open blocking incidents.")
    parser.add_argument("--require-current-hub", action="store_true", help="Verifier requires current Hub verification evidence.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_trust_operations_incident_knowledge_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, run, export, and verify Trust Operations Incident Knowledge regression guards.")
    parser.add_argument("--hub-id", default="hub", help="Trust Operations Hub id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh Knowledge entries from closed incidents.")
    parser.add_argument("--list-entries", action="store_true", help="List Knowledge entries.")
    parser.add_argument("--entry-id", default=None, help="Knowledge entry id.")
    parser.add_argument("--hide-entry", action="store_true", help="Hide a Knowledge entry.")
    parser.add_argument("--unhide-entry", action="store_true", help="Unhide a Knowledge entry.")
    parser.add_argument("--create-guard", action="store_true", help="Create a regression guard for a Knowledge entry.")
    parser.add_argument("--guard-id", default=None, help="Regression guard id.")
    parser.add_argument("--guard-type", default=None, help="Regression guard type.")
    parser.add_argument("--run-guard", action="store_true", help="Run a single regression guard.")
    parser.add_argument("--run-all-guards", action="store_true", help="Run all regression guards.")
    parser.add_argument("--refresh-recurrence", action="store_true", help="Refresh incident recurrence report.")
    parser.add_argument("--export", action="store_true", help="Export the Knowledge package directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Knowledge ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Knowledge ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-guards-passed", action="store_true", help="Verifier requires passed guard runs.")
    parser.add_argument("--require-no-open-recurrence", action="store_true", help="Verifier requires no open recurrence.")
    parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_trust_operations_controls_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, assess, export, and verify Trust Operations Controls.")
    parser.add_argument("--hub-id", default="hub", help="Trust Operations Hub id.")
    parser.add_argument("--policy-id", default=None, help="Control policy id.")
    parser.add_argument("--assessment-id", default=None, help="Control assessment id.")
    parser.add_argument("--refresh-catalog", action="store_true", help="Refresh the Control Catalog.")
    parser.add_argument("--create-policy", action="store_true", help="Create a Control Policy Bundle.")
    parser.add_argument("--policy-name", default="Default Trust Operations Controls", help="Control policy display name.")
    parser.add_argument("--assess", action="store_true", help="Assess a Control Policy Bundle.")
    parser.add_argument("--export", action="store_true", help="Export the Control package directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Control ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Control ZIP.")
    parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-policy-passed", action="store_true", help="Verifier requires the control policy assessment to pass.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


def build_public_trust_center_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build local MusicForge Public Trust Center reports and packages.")
    parser.add_argument("--center-id", default="ptc-default", help="Public Trust Center id.")
    parser.add_argument("--name", default=None, help="Display name.")
    parser.add_argument("--release-id", action="append", dest="release_ids", default=[], help="Release id to include. Can be repeated.")
    parser.add_argument("--portfolio-id", action="append", dest="portfolio_ids", default=[], help="Portfolio id to include. Can be repeated.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Public Trust Center report.")
    parser.add_argument("--export", action="store_true", help="Build the static Trust Center export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Public Trust Center ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Public Trust Center ZIP.")
    parser.add_argument("--archive", action="store_true", help="Append an archive event for the current ZIP.")
    parser.add_argument("--anchor-register", action="store_true", help="Register the current delivery anchor in the Anchor Registry.")
    parser.add_argument("--anchor-publish", action="store_true", help="Publish the current Anchor Registry entry.")
    parser.add_argument("--anchor-revoke", default=None, help="Revoke an Anchor Registry entry id.")
    parser.add_argument("--anchor-export", action="store_true", help="Export the Anchor Registry package directory.")
    parser.add_argument("--anchor-zip", action="store_true", help="Build the Anchor Registry ZIP.")
    parser.add_argument("--anchor-verify", action="store_true", help="Verify the Anchor Registry ZIP.")
    parser.add_argument("--anchor-reason", default="Public Trust Center anchor registry operation", help="Reason for Anchor Registry state changes.")
    parser.add_argument("--anchor-transparency-refresh", action="store_true", help="Refresh the Anchor Transparency ledger/report.")
    parser.add_argument("--anchor-checkpoint-create", action="store_true", help="Create the current Anchor Transparency checkpoint.")
    parser.add_argument("--anchor-transparency-export", action="store_true", help="Export the Anchor Transparency package directory.")
    parser.add_argument("--anchor-transparency-zip", action="store_true", help="Build the Anchor Transparency ZIP.")
    parser.add_argument("--anchor-transparency-verify", action="store_true", help="Verify the Anchor Transparency ZIP.")
    parser.add_argument("--distribution-kit-refresh", action="store_true", help="Refresh the Public Trust Center Distribution Kit report.")
    parser.add_argument("--distribution-kit-export", action="store_true", help="Export the Public Trust Center Distribution Kit directory.")
    parser.add_argument("--distribution-kit-zip", action="store_true", help="Build the Public Trust Center Distribution Kit ZIP.")
    parser.add_argument("--distribution-kit-verify", action="store_true", help="Verify the Public Trust Center Distribution Kit ZIP.")
    parser.add_argument("--distribution-kit-acceptance-template", action="store_true", help="Create a Distribution Kit external acceptance response template.")
    parser.add_argument("--distribution-kit-acceptance-response-file", type=Path, default=None, help="Import a Distribution Kit acceptance response JSON file.")
    parser.add_argument("--distribution-kit-acceptance-response-base64", default=None, help="Import a base64-encoded Distribution Kit acceptance response.")
    parser.add_argument("--distribution-kit-acceptance-response-id", default=None, help="Distribution Kit acceptance response id.")
    parser.add_argument("--distribution-kit-acceptance-verify-response", action="store_true", help="Verify an imported Distribution Kit acceptance response.")
    parser.add_argument("--distribution-kit-accepted-evidence-export", action="store_true", help="Export accepted Distribution Kit evidence for the response.")
    parser.add_argument("--distribution-kit-accepted-evidence-zip", action="store_true", help="Build accepted Distribution Kit evidence ZIP for the response.")
    parser.add_argument("--distribution-kit-accepted-evidence-verify", action="store_true", help="Verify the accepted Distribution Kit evidence ZIP.")
    parser.add_argument("--distribution-kit-acceptance-change-request", action="store_true", help="Create a draft follow-up from a needs_changes/rejected Distribution Kit response.")
    parser.add_argument("--acceptance-board-policy-save", type=Path, default=None, help="Save Acceptance Board policy from a JSON file.")
    parser.add_argument("--acceptance-board-refresh", action="store_true", help="Refresh the Acceptance Board report.")
    parser.add_argument("--acceptance-board-export", action="store_true", help="Export the Acceptance Board directory.")
    parser.add_argument("--acceptance-board-zip", action="store_true", help="Build the Acceptance Board ZIP.")
    parser.add_argument("--acceptance-board-verify", action="store_true", help="Verify the Acceptance Board ZIP.")
    parser.add_argument("--acceptance-board-signoff-draft", action="store_true", help="Create an Acceptance Board signoff draft.")
    parser.add_argument("--acceptance-board-signoff", action="store_true", help="Sign the current ready Acceptance Board.")
    parser.add_argument("--acceptance-board-signed-by", default="MusicForge Operator", help="Signer name for Acceptance Board signoff.")
    parser.add_argument("--acceptance-board-signoff-reason", default="Acceptance Board ready for public release.", help="Reason for Acceptance Board signoff.")
    parser.add_argument("--acceptance-board-change-request-create", action="store_true", help="Create an Acceptance Board signoff Change Request.")
    parser.add_argument("--acceptance-board-change-request-approve", action="store_true", help="Approve an Acceptance Board signoff Change Request.")
    parser.add_argument("--acceptance-board-change-request-id", default=None, help="Acceptance Board Change Request id.")
    parser.add_argument("--acceptance-board-reset-signoff", action="store_true", help="Reset Acceptance Board signoff using an approved Change Request.")
    parser.add_argument("--acceptance-board-signoff-archive-export", action="store_true", help="Export the Acceptance Board signoff archive directory.")
    parser.add_argument("--acceptance-board-signoff-archive-zip", action="store_true", help="Build the Acceptance Board signoff archive ZIP.")
    parser.add_argument("--acceptance-board-signoff-archive-verify", action="store_true", help="Verify the Acceptance Board signoff archive ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-ready", action="store_true", help="Verifier requires ready board/package state.")
    parser.add_argument("--require-quorum", action="store_true", help="Verifier requires board quorum.")
    parser.add_argument("--require-no-conflicts", action="store_true", help="Verifier requires no board conflicts.")
    parser.add_argument("--min-accepted-count", type=int, default=0, help="Minimum accepted evidence count required by the verifier.")
    parser.add_argument("--min-accepted-organizations", type=int, default=0, help="Minimum accepted organization count required by the verifier.")
    parser.add_argument("--required-role", action="append", dest="required_roles", default=[], help="Required Acceptance Board role. Can be repeated.")
    parser.add_argument("--require-registry-current", action="store_true", help="Require current Registry evidence.")
    parser.add_argument("--require-portal-current", action="store_true", help="Require current Portal evidence.")
    parser.add_argument("--require-transparency-current", action="store_true", help="Require current Transparency evidence.")
    parser.add_argument("--require-acknowledgement-current", action="store_true", help="Require current accepted acknowledgement evidence.")
    parser.add_argument("--include-delivery", dest="include_delivery", action="store_true", default=True, help="Include delivery chain summaries.")
    parser.add_argument("--no-include-delivery", dest="include_delivery", action="store_false", help="Do not include delivery chain summaries.")
    parser.add_argument("--include-distribution", dest="include_distribution", action="store_true", default=True, help="Include Distribution target summaries.")
    parser.add_argument("--no-include-distribution", dest="include_distribution", action="store_false", help="Do not include Distribution target summaries.")
    parser.add_argument("--include-submission", dest="include_submission", action="store_true", default=True, help="Include Submission batch summaries.")
    parser.add_argument("--no-include-submission", dest="include_submission", action="store_false", help="Do not include Submission batch summaries.")
    parser.add_argument("--include-submission-evidence", dest="include_submission_evidence", action="store_true", default=True, help="Include Submission Evidence summaries.")
    parser.add_argument("--no-include-submission-evidence", dest="include_submission_evidence", action="store_false", help="Do not include Submission Evidence summaries.")
    parser.add_argument("--include-operations", dest="include_operations", action="store_true", default=True, help="Include Release Operations summaries.")
    parser.add_argument("--no-include-operations", dest="include_operations", action="store_false", help="Do not include Release Operations summaries.")
    parser.add_argument("--require-release-signoff", dest="require_release_signoff", action="store_true", default=True, help="Require Release Signoff in the Trust Center report.")
    parser.add_argument("--no-require-release-signoff", dest="require_release_signoff", action="store_false", help="Do not require Release Signoff in the Trust Center report.")
    parser.add_argument("--require-distribution-signed", action="store_true", help="Require signed and verified Distribution packages in the report.")
    parser.add_argument("--require-submission-accepted", action="store_true", help="Require accepted Submission batches in the report.")
    parser.add_argument("--require-submission-evidence-signed", action="store_true", help="Require signed Submission Evidence packages in the report.")
    parser.add_argument("--require-operations-signed", action="store_true", help="Require Release Operations Signoff in the report.")
    parser.add_argument("--require-operations-audit-verified", action="store_true", help="Require verified Release Operations Audit evidence in the report.")
    parser.add_argument("--require-operations-reviewer-pack-verified", action="store_true", help="Require verified Release Operations Reviewer Pack evidence in the report.")
    parser.add_argument("--require-release-readiness", action="store_true", help="Verifier requires selected releases to be ready.")
    parser.add_argument("--require-delivery-readiness", action="store_true", help="Verifier requires delivery readiness.")
    parser.add_argument("--require-distribution-ready", action="store_true", help="Verifier requires distribution readiness.")
    parser.add_argument("--require-submission-evidence", action="store_true", help="Verifier requires submission evidence.")
    parser.add_argument("--require-operations-audit", action="store_true", help="Verifier requires operations audit evidence.")
    parser.add_argument("--require-operations-reviewer-pack", action="store_true", help="Verifier requires operations reviewer pack evidence.")
    parser.add_argument("--require-anchor-registry-current", action="store_true", help="Verifier requires current Anchor Registry evidence.")
    parser.add_argument("--require-anchor-published", action="store_true", help="Verifier requires a published Anchor Registry current entry.")
    parser.add_argument("--require-anchor-not-revoked", action="store_true", help="Verifier requires the Anchor Registry current entry not to be revoked.")
    parser.add_argument("--require-anchor-transparency-current", action="store_true", help="Verifier requires current Anchor Transparency evidence.")
    parser.add_argument("--require-anchor-checkpoint", action="store_true", help="Verifier requires an external Anchor Transparency checkpoint.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser


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


def build_release_encode_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render local encoded audio derivatives for a Release.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--profiles", default="wav_master", help="Comma-separated audio encoding profile ids.")
    parser.add_argument("--force", action="store_true", help="Re-render existing encoded audio.")
    parser.add_argument("--json", action="store_true", help="Print result JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write result JSON.")
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


def build_acceptance_fix_plan_parser() -> argparse.ArgumentParser:
    plan_parser = argparse.ArgumentParser(description="Manage local MusicForge knowledge-assisted Acceptance Fix Plans.")
    subparsers = plan_parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="Create a Fix Plan from Acceptance Analytics and KB history.")
    create.add_argument("--analytics-report-id", required=True, help="Source Acceptance Analytics report id.")
    create.add_argument("--kb-report-id", default=None, help="Optional Acceptance KB report id.")
    create.add_argument("--max-items", type=int, default=20, help="Maximum planned items.")
    create.add_argument("--include-hidden-kb", action="store_true", help="Allow hidden KB entries in planning evidence.")

    subparsers.add_parser("list", help="List Fix Plans.").add_argument("--include-archived", action="store_true")

    show = subparsers.add_parser("show", help="Show a Fix Plan.")
    show.add_argument("plan_id")

    refresh = subparsers.add_parser("refresh", help="Refresh an existing Fix Plan.")
    refresh.add_argument("plan_id")

    create_sprint = subparsers.add_parser("create-fix-sprint", help="Create a Fix Sprint from a Fix Plan.")
    create_sprint.add_argument("plan_id")
    create_sprint.add_argument("--name", default=None)
    create_sprint.add_argument("--planned-item-id", action="append", dest="planned_item_ids", default=[])
    create_sprint.add_argument("--profile", default=None)

    review = subparsers.add_parser("review", help="Show or refresh a Fix Plan Outcome Review.")
    review.add_argument("plan_id")
    review.add_argument("--refresh", action="store_true")

    recommend = subparsers.add_parser("recommend", help="Preview a non-persisted Fix Plan.")
    recommend.add_argument("--analytics-report-id", required=True)
    recommend.add_argument("--kb-report-id", default=None)
    recommend.add_argument("--max-items", type=int, default=20)
    recommend.add_argument("--include-hidden-kb", action="store_true")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return plan_parser


def build_planning_ruleset_parser() -> argparse.ArgumentParser:
    ruleset_parser = argparse.ArgumentParser(description="Manage local MusicForge Planning Rule Sets.")
    subparsers = ruleset_parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="Create a Planning Rule Set.")
    create.add_argument("--template", default="baseline", help="Template: baseline, manual_conservative, kb_trust_light, waiver_strict, synthetic_strict.")
    create.add_argument("--name", default=None)
    create.add_argument("--description", default=None)

    subparsers.add_parser("list", help="List Planning Rule Sets.").add_argument("--include-archived", action="store_true")

    show = subparsers.add_parser("show", help="Show a Planning Rule Set.")
    show.add_argument("ruleset_id")

    clone = subparsers.add_parser("clone", help="Clone a Planning Rule Set.")
    clone.add_argument("ruleset_id")
    clone.add_argument("--name", default=None)

    archive = subparsers.add_parser("archive", help="Archive a Planning Rule Set.")
    archive.add_argument("ruleset_id")

    validate = subparsers.add_parser("validate", help="Validate a Planning Rule Set.")
    validate.add_argument("ruleset_id")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return ruleset_parser


def build_planning_simulation_parser() -> argparse.ArgumentParser:
    simulation_parser = argparse.ArgumentParser(description="Run local MusicForge Planning Rule Simulations.")
    subparsers = simulation_parser.add_subparsers(dest="action", required=True)

    run = subparsers.add_parser("run", help="Run a Planning Rule Simulation.")
    run.add_argument("--ruleset-id", required=True)
    run.add_argument("--release-id", default=None)
    run.add_argument("--project-id", default=None)
    run.add_argument("--review-id", action="append", dest="review_ids", default=[])
    run.add_argument("--include-warning-reviews", action="store_true", default=True)
    run.add_argument("--exclude-synthetic-only", action="store_true")

    show = subparsers.add_parser("show", help="Show a Planning Rule Simulation.")
    show.add_argument("simulation_id")

    refresh = subparsers.add_parser("refresh", help="Refresh a Planning Rule Simulation.")
    refresh.add_argument("simulation_id")

    archive = subparsers.add_parser("archive", help="Archive a Planning Rule Simulation.")
    archive.add_argument("simulation_id")

    subparsers.add_parser("list", help="List Planning Rule Simulations.").add_argument("--include-archived", action="store_true")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return simulation_parser


def build_planning_rule_governance_parser() -> argparse.ArgumentParser:
    governance_parser = argparse.ArgumentParser(description="Govern local MusicForge Planning Rule promotions and active versions.")
    subparsers = governance_parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("active", help="Show the current active Planning Rule Version.")
    subparsers.add_parser("versions", help="List Planning Rule Versions.").add_argument("--include-archived", action="store_true")

    version = subparsers.add_parser("version", help="Show one Planning Rule Version.")
    version.add_argument("version_id")

    subparsers.add_parser("promotions", help="List Planning Rule Promotions.").add_argument("--include-archived", action="store_true")

    promotion = subparsers.add_parser("promotion", help="Show one Planning Rule Promotion.")
    promotion.add_argument("promotion_id")

    request = subparsers.add_parser("promote-request", help="Create a Planning Rule Promotion request.")
    request.add_argument("--ruleset-id", required=True)
    request.add_argument("--simulation-id", required=True)
    request.add_argument("--note", default="")

    approve = subparsers.add_parser("approve", help="Approve a Planning Rule Promotion.")
    approve.add_argument("promotion_id")
    approve.add_argument("--approved-by", default="developer")
    approve.add_argument("--note", default="")
    approve.add_argument("--force", action="store_true")
    approve.add_argument("--override-reason", default="")

    reject = subparsers.add_parser("reject", help="Reject a Planning Rule Promotion.")
    reject.add_argument("promotion_id")
    reject.add_argument("--rejected-by", default="developer")
    reject.add_argument("--reason", required=True)

    promote = subparsers.add_parser("promote", help="Promote an approved Planning Rule Promotion to active.")
    promote.add_argument("promotion_id")
    promote.add_argument("--promoted-by", default="developer")
    promote.add_argument("--activation-note", default="")

    rollback = subparsers.add_parser("rollback", help="Rollback active Planning Rules to a previous version.")
    rollback.add_argument("--target-version-id", required=True)
    rollback.add_argument("--rolled-back-by", default="developer")
    rollback.add_argument("--reason", required=True)

    subparsers.add_parser("events", help="List Planning Rule Governance events.").add_argument("--limit", type=int, default=50)

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return governance_parser


def build_planning_rule_impact_parser() -> argparse.ArgumentParser:
    impact_parser = argparse.ArgumentParser(description="Monitor active MusicForge Planning Rule impact.")
    subparsers = impact_parser.add_subparsers(dest="action", required=True)

    refresh = subparsers.add_parser("refresh", help="Refresh a Planning Rule Impact report.")
    refresh.add_argument("--release-id", default=None)
    refresh.add_argument("--project-id", default=None)
    refresh.add_argument("--include-legacy", action="store_true", default=True)
    refresh.add_argument("--exclude-legacy", action="store_true")
    refresh.add_argument("--include-superseded", action="store_true", default=True)
    refresh.add_argument("--exclude-superseded", action="store_true")

    listing = subparsers.add_parser("list", help="List Planning Rule Impact reports.")
    listing.add_argument("--include-archived", action="store_true")
    listing.add_argument("--release-id", default=None)
    listing.add_argument("--project-id", default=None)

    show = subparsers.add_parser("show", help="Show one Planning Rule Impact report.")
    show.add_argument("report_id")

    refresh_existing = subparsers.add_parser("refresh-existing", help="Refresh an existing Planning Rule Impact report.")
    refresh_existing.add_argument("report_id")

    archive = subparsers.add_parser("archive", help="Archive a Planning Rule Impact report.")
    archive.add_argument("report_id")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return impact_parser


def build_acceptance_kb_parser() -> argparse.ArgumentParser:
    kb_parser = argparse.ArgumentParser(description="Manage the local MusicForge Acceptance Knowledge Base.")
    subparsers = kb_parser.add_subparsers(dest="action", required=True)

    refresh = subparsers.add_parser("refresh", help="Refresh Acceptance KB entries and report.")
    refresh.add_argument("--project-id", default=None)
    refresh.add_argument("--release-id", default=None)

    subparsers.add_parser("report", help="Show the latest Acceptance KB report.")

    entries = subparsers.add_parser("entries", help="List Acceptance KB entries.")
    entries.add_argument("--include-hidden", action="store_true")

    show = subparsers.add_parser("show", help="Show one Acceptance KB entry.")
    show.add_argument("entry_id")

    search = subparsers.add_parser("search", help="Search Acceptance KB entries.")
    search.add_argument("--issue-type", default=None)
    search.add_argument("--style", default=None)
    search.add_argument("--song-id", default=None)
    search.add_argument("--project-id", default=None)
    search.add_argument("--release-id", default=None)
    search.add_argument("--outcome-status", default=None)

    recommend = subparsers.add_parser("recommend", help="Recommend next actions from Acceptance KB history.")
    recommend.add_argument("--issue-type", action="append", dest="issue_types", default=[])
    recommend.add_argument("--style", default=None)
    recommend.add_argument("--song-id", default=None)
    recommend.add_argument("--project-id", default=None)
    recommend.add_argument("--release-id", default=None)

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return kb_parser


def _add_generate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "request",
        type=Path,
        nargs="?",
        help="Path to a song request JSON file.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Run output directory. Defaults to runs/<request-title-slug>.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the normalized request without calling an LLM.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip graph steps whose expected artifacts already exist.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing output directory instead of resuming it.",
    )
    parser.add_argument(
        "--pipeline-mode",
        choices=["single", "multinode"],
        default="single",
        help="Pipeline to run: single or multinode.",
    )


def _trust_operations_assurance_source_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "hub_package_path": getattr(args, "hub_package", None),
        "hub_verification_report_path": getattr(args, "hub_verification_report", None),
        "control_signoff_archive_path": getattr(args, "control_signoff_archive", None),
        "control_signoff_verification_report_path": getattr(args, "control_signoff_verification_report", None),
        "control_package_path": getattr(args, "control_package", None),
        "control_verification_report_path": getattr(args, "control_verification_report", None),
        "incident_board_package_path": getattr(args, "incident_board_package", None),
        "incident_board_verification_report_path": getattr(args, "incident_board_verification_report", None),
        "incident_knowledge_package_path": getattr(args, "incident_knowledge_package", None),
        "incident_knowledge_verification_report_path": getattr(args, "incident_knowledge_verification_report", None),
        "release_verification_paths": getattr(args, "release_verification", []),
        "distribution_verification_paths": getattr(args, "distribution_verification", []),
        "submission_verification_paths": getattr(args, "submission_verification", []),
        "submission_evidence_verification_paths": getattr(args, "submission_evidence_verification", []),
        "release_operations_verification_paths": getattr(args, "release_operations_verification", []),
    }


def _add_trust_operations_assurance_watch_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--assurance-archive", type=Path, default=None, help="External Trust Operations Continuous Assurance Archive ZIP.")
    parser.add_argument("--assurance-verification-report", type=Path, default=None, help="External Trust Operations Continuous Assurance verification report.")
    parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")


def _trust_operations_assurance_watch_source_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "assurance_archive_path": getattr(args, "assurance_archive", None),
        "assurance_verification_report_path": getattr(args, "assurance_verification_report", None),
        "hub_package_path": getattr(args, "hub_package", None),
        "hub_verification_report_path": getattr(args, "hub_verification_report", None),
    }


def _add_trust_operations_final_readiness_source_args(parser: argparse.ArgumentParser) -> None:
    _add_trust_operations_assurance_source_args(parser)
    parser.add_argument("--continuous-assurance-archive", type=Path, default=None, help="External Trust Operations Continuous Assurance Archive ZIP.")
    parser.add_argument("--continuous-assurance-verification-report", type=Path, default=None, help="External Trust Operations Continuous Assurance verification report.")
    parser.add_argument("--assurance-watch-package", type=Path, default=None, help="External Trust Operations Assurance Watch ZIP.")
    parser.add_argument("--assurance-watch-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch verification report.")
    parser.add_argument("--assurance-watch-signoff-archive", type=Path, default=None, help="External Trust Operations Assurance Watch Signoff Archive ZIP.")
    parser.add_argument("--assurance-watch-signoff-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch Signoff verification report.")


def _trust_operations_final_readiness_source_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload = _trust_operations_assurance_source_payload(args)
    payload.update(
        {
            "continuous_assurance_archive_path": getattr(args, "continuous_assurance_archive", None),
            "continuous_assurance_verification_report_path": getattr(args, "continuous_assurance_verification_report", None),
            "assurance_watch_package_path": getattr(args, "assurance_watch_package", None),
            "assurance_watch_verification_report_path": getattr(args, "assurance_watch_verification_report", None),
            "assurance_watch_signoff_archive_path": getattr(args, "assurance_watch_signoff_archive", None),
            "assurance_watch_signoff_verification_report_path": getattr(args, "assurance_watch_signoff_verification_report", None),
        }
    )
    return payload


def main() -> None:
    try:
        _main()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _run_maintenance_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.lts_maintenance import LTSMaintenanceStore, MAINTENANCE_PROFILES

    store = LTSMaintenanceStore()
    if args.section == "status":
        return store.status()
    if args.section == "backup":
        if args.backup_action == "create":
            result = store.backups.create_backup(mode=args.mode)
            return {"status": result.get("verification", {}).get("status") or "unknown", **result}
        if args.backup_action == "list":
            return {"status": "passed", "backups": store.backups.list_backups()}
        if args.backup_action == "verify":
            verification = store.backups.verify_backup(args.backup_id)
            return {"status": verification.get("status"), "backup_id": args.backup_id, "verification": verification}
        if args.backup_action == "restore-plan":
            plan = store.backups.restore_plan(backup_id=args.backup_id, zip_path=args.zip_path, target=args.target)
            return {"status": plan.get("status"), "restore_plan": plan}
        if args.backup_action == "restore":
            result = store.backups.restore(
                backup_id=args.backup_id,
                zip_path=args.zip_path,
                target=args.target,
                confirm=args.confirm,
                overwrite=args.overwrite,
                allow_current_workspace=args.allow_current_workspace,
            )
            return {"status": result.get("status"), **result}
    if args.section == "upgrade" and args.upgrade_action == "preflight":
        report = store.run_upgrade_preflight(target_version=args.target_version, require_verified_backup=args.require_verified_backup, allow_dirty=args.allow_dirty)
        return {"status": report.get("status"), "preflight": report}
    if args.section == "migration":
        if args.migration_action == "status":
            return {"status": "passed", "migration": store.migration_status()}
        if args.migration_action == "plan":
            return {"status": "passed", "migration_plan": store.migration_plan()}
        if args.migration_action == "run":
            result = store.run_migrations(require_backup=args.require_backup)
            return {"status": "passed", **result}
    if args.section == "check":
        if args.check_action == "list":
            return {"status": "passed", "profiles": sorted(MAINTENANCE_PROFILES), "runs": store.list_check_runs()}
        if args.check_action == "run":
            report = store.run_check(profile=args.profile)
            return {"status": report.get("status"), "report": report}
        if args.check_action == "show":
            path = store.check_runs_dir / args.check_id / "maintenance-check-report.json"
            return {"status": "passed", "report": read_json(path)}
    raise ValueError("Unsupported maintenance command.")


def _print_maintenance_result(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    status = result.get("status") or result.get("report", {}).get("status") or result.get("verification", {}).get("status") or "unknown"
    print(f"MusicForge LTS Maintenance: {status}")
    if "backup" in result:
        backup = result.get("backup") or {}
        print(f"backup: {backup.get('backup_id')} {backup.get('verification_status') or backup.get('status')}")
    if "verification" in result:
        verification = result.get("verification") or {}
        print(f"verification: {verification.get('status')} blockers={(verification.get('summary') or {}).get('blocker_count')}")
    if "restore_plan" in result:
        plan = result.get("restore_plan") or {}
        print(f"restore plan: {plan.get('status')} actions={len(plan.get('actions') or [])}")
    if "preflight" in result:
        preflight = result.get("preflight") or {}
        print(f"preflight: {preflight.get('preflight_id')} {preflight.get('status')}")
    if "migration" in result:
        migration = result.get("migration") or {}
        print(f"migration: {migration.get('status')} applied={len(migration.get('applied') or [])}")
    if "report" in result:
        report = result.get("report") or {}
        print(f"report: {report.get('check_id')} {report.get('profile')} {report.get('status')}")


def _run_audio_lab_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.audio_lab import AudioLabStore

    store = AudioLabStore()
    if args.section == "status":
        return {"ok": True, "environment": store.environment_status()}
    if args.section == "detect":
        return {"ok": True, "environment": store.detect_environment()}
    if args.section == "test-profile":
        result = store.test_profile(args.profile_id)
        return {"ok": result.get("status") != "failed", "profile_test": result, "status": result.get("status")}
    if args.section == "setup-report":
        report = store.setup_report()
        if args.report_out is not None:
            write_json(args.report_out, report)
        return {"ok": True, "setup_report": report, "status": report.get("status")}
    if args.section == "smoke":
        report = store.run_smoke({"cases": args.cases, "render_audio": args.render_audio, "profile_id": args.profile_id})
        if args.report_out is not None:
            write_json(args.report_out, report)
        return {"ok": report.get("status") != "failed", "smoke_run": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.section == "smoke-report":
        report = store.read_smoke_report(args.smoke_run_id)
        if args.report_out is not None:
            write_json(args.report_out, report)
        return {"ok": True, "smoke_run": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.section == "session":
        if args.session_action == "create":
            session = store.create_session({"from_smoke": args.from_smoke})
            return {"ok": True, "session": session, "summary": session.get("summary", {}), "status": session.get("status")}
        if args.session_action == "list":
            sessions = store.list_sessions()
            return {"ok": True, "sessions": sessions, "summary": {"session_count": len(sessions)}, "status": "passed"}
        if args.session_action == "detail":
            session = store.read_session(args.session_id)
            return {"ok": True, "session": session, "summary": session.get("summary", {}), "status": session.get("status")}
        if args.session_action == "review":
            result = store.write_item_review(
                args.session_id,
                args.item_id,
                {
                    "result": args.result,
                    "rating": args.rating,
                    "reviewer": {"name": args.reviewer, "role": args.role},
                    "notes": args.notes,
                    "playback_confirmed": args.playback_confirmed,
                },
            )
            return {"ok": True, **result, "status": result.get("session", {}).get("status")}
        if args.session_action == "marker":
            result = store.add_marker(args.session_id, args.item_id, {"time_seconds": args.time_seconds, "category": args.category, "severity": args.severity, "message": args.message})
            return {"ok": True, **result, "status": result.get("session", {}).get("status")}
        if args.session_action == "create-review-task":
            return {"ok": True, **store.create_marker_draft(args.session_id, args.marker_id, "review_task", {"title": args.title, "instruction": args.instruction}), "status": "draft"}
        if args.session_action == "create-audio-revision-draft":
            return {"ok": True, **store.create_marker_draft(args.session_id, args.marker_id, "audio_revision", {"title": args.title, "instruction": args.instruction}), "status": "draft"}
        if args.session_action == "create-mix-patch-draft":
            return {"ok": True, **store.create_marker_draft(args.session_id, args.marker_id, "mix_patch", {"title": args.title, "instruction": args.instruction}), "status": "draft"}
        if args.session_action == "report":
            report = store.session_report(args.session_id)
            return {"ok": report.get("status") != "failed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
        if args.session_action == "close":
            result = store.close_session(args.session_id, {"closed_by": args.closed_by})
            return {"ok": True, **result, "status": result.get("session", {}).get("status")}
    if args.section == "compare":
        if args.compare_action == "create":
            comparison = store.create_comparison({"left": args.left, "right": args.right})
            return {"ok": True, "comparison": comparison, "status": "created"}
        if args.compare_action == "review":
            comparison = store.review_comparison(
                args.comparison_id,
                {
                    "preferred": args.preferred,
                    "rating": args.rating,
                    "rating_delta": args.rating_delta,
                    "reviewer": {"name": args.reviewer, "role": args.role},
                    "notes": args.notes,
                    "playback_confirmed": args.playback_confirmed,
                },
            )
            return {"ok": True, "comparison": comparison, "status": "reviewed"}
        if args.compare_action == "report":
            report = store.comparison_report(args.comparison_id)
            return {"ok": report.get("status") != "failed", "report": report, "status": report.get("status")}
    raise ValueError("Unsupported audio-lab command.")


def _run_audio_fix_sprint_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.audio_fix_sprints import AudioFixSprintStore

    store = AudioFixSprintStore()
    if args.action == "create":
        sprint = store.create_sprint({"session_ids": args.session_ids, "name": args.name, "include_test_audio": args.include_test_audio})
        return {"ok": True, "sprint": sprint, "summary": sprint.get("summary", {}), "status": sprint.get("status")}
    if args.action == "list":
        sprints = store.list_sprints()
        return {"ok": True, "sprints": sprints, "summary": {"sprint_count": len(sprints)}, "status": "passed"}
    if args.action == "detail":
        sprint = store.read_sprint(args.sprint_id)
        return {"ok": True, "sprint": sprint, "summary": sprint.get("summary", {}), "status": sprint.get("status")}
    if args.action == "refresh":
        sprint = store.refresh_sprint(args.sprint_id)
        return {"ok": True, "sprint": sprint, "summary": sprint.get("summary", {}), "status": sprint.get("status")}
    if args.action == "create-drafts":
        result = store.create_drafts(args.sprint_id, {"draft_type": args.draft_type, "item_ids": args.item_ids or []})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    if args.action == "generate-candidates":
        result = store.generate_candidates(args.sprint_id, {"item_ids": args.item_ids or []})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    if args.action == "review-candidate":
        result = store.review_candidate(
            args.sprint_id,
            args.item_id,
            args.candidate_id,
            {
                "preferred": args.preferred,
                "rating": args.rating,
                "rating_delta": args.rating_delta,
                "reviewer": {"name": args.reviewer, "role": args.role},
                "notes": args.notes,
                "playback_confirmed": args.playback_confirmed,
            },
        )
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("candidate", {}).get("status")}
    if args.action == "select-candidate":
        result = store.select_candidate(args.sprint_id, args.item_id, args.candidate_id, {"selected_by": args.selected_by})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    if args.action == "create-recheck-session":
        result = store.create_recheck_session(args.sprint_id)
        return {"ok": True, **result, "summary": result.get("recheck_session", {}).get("summary", {}), "status": result.get("recheck_session", {}).get("status")}
    if args.action == "review-recheck":
        result = store.review_recheck_item(
            args.sprint_id,
            args.item_id,
            {
                "result": args.result,
                "rating": args.rating,
                "reviewer": {"name": args.reviewer, "role": args.role},
                "notes": args.notes,
                "playback_confirmed": args.playback_confirmed,
            },
        )
        return {"ok": True, **result, "summary": result.get("recheck_session", {}).get("summary", {}), "status": result.get("recheck_session", {}).get("status")}
    if args.action == "closeout":
        report = store.closeout_report(args.sprint_id)
        return {"ok": report.get("status") == "passed", "closeout": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "close":
        result = store.close_sprint(args.sprint_id, {"closed_by": args.closed_by})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    raise ValueError("Unsupported audio-fix-sprint command.")


def _run_audio_campaign_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.audio_campaigns import AudioCampaignStore
    from song_agent.audio_campaign_verifier import write_audio_campaign_verification_report
    from song_agent.audio_campaign_governance import AudioCampaignGovernanceStore
    from song_agent.audio_campaign_archive_verifier import write_audio_campaign_archive_verification_report
    from song_agent.audio_campaign_planner import AudioCampaignPlannerStore
    from song_agent.audio_campaign_remediation import AudioCampaignRemediationStore
    from song_agent.audio_campaign_remediation_verifier import write_audio_campaign_remediation_verification_report

    store = AudioCampaignStore()
    governance_store = AudioCampaignGovernanceStore(campaign_store=store)
    planner_store = AudioCampaignPlannerStore(audio_lab_store=store.audio_lab_store, audio_campaign_store=store)
    remediation_store = AudioCampaignRemediationStore(planner_store=planner_store, campaign_store=store, fix_sprint_store=store.audio_fix_sprint_store)
    if args.action == "plan-release":
        plan = planner_store.refresh_plan(args.release_id)
        return {"ok": plan.get("status") != "blocked", "plan": plan, "summary": plan.get("preflight_summary", {}), "status": plan.get("status")}
    if args.action == "preflight-release":
        preflight = planner_store.preflight(args.release_id)
        return {"ok": preflight.get("status") == "passed", "preflight": preflight, "summary": preflight.get("summary", {}), "status": preflight.get("status")}
    if args.action == "create-from-release":
        result = planner_store.create_campaign_from_release(args.release_id, {"name": args.name, "minimum_rating": args.minimum_rating, "allow_failed_preflight": args.allow_failed_preflight})
        return {"ok": True, **result, "summary": result.get("link", {}).get("coverage", {}), "status": result.get("campaign", {}).get("status")}
    if args.action == "release-status":
        status = planner_store.status(args.release_id)
        return {"ok": status.get("status") != "failed", **status}
    if args.action == "release-link":
        link = planner_store.link_campaign(args.release_id, args.campaign_id)
        return {"ok": True, "link": link, "summary": link.get("coverage", {}), "status": link.get("coverage_status")}
    if args.action == "create":
        campaign = store.create_campaign(
            {
                "session_ids": args.session_ids,
                "name": args.name,
                "profile": args.profile,
                "allow_test_audio": args.allow_test_audio,
                "allow_synthetic_review": args.allow_synthetic_review,
                "minimum_rating": args.minimum_rating,
            }
        )
        return {"ok": True, "campaign": campaign, "summary": campaign.get("summary", {}), "status": campaign.get("status")}
    if args.action == "list":
        campaigns = store.list_campaigns()
        return {"ok": True, "campaigns": campaigns, "summary": {"campaign_count": len(campaigns)}, "status": "passed"}
    if args.action == "detail":
        campaign = store.read_campaign(args.campaign_id)
        return {"ok": True, "campaign": campaign, "summary": campaign.get("summary", {}), "status": campaign.get("status")}
    if args.action == "refresh":
        campaign = store.refresh_campaign(args.campaign_id)
        return {"ok": True, "campaign": campaign, "summary": campaign.get("summary", {}), "status": campaign.get("status")}
    if args.action == "link-session":
        campaign = store.link_listening_session(args.campaign_id, args.session_id)
        return {"ok": True, "campaign": campaign, "summary": campaign.get("summary", {}), "status": campaign.get("status")}
    if args.action == "create-fix-sprints":
        result = store.create_fix_sprints(args.campaign_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("report", {}).get("summary", {})}
    if args.action == "report":
        report = store.refresh_report(args.campaign_id)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "signoff":
        result = store.signoff(args.campaign_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("report", {}).get("summary", {})}
    if args.action == "export":
        result = store.export_campaign(args.campaign_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {})}
    if args.action == "zip":
        result = store.build_zip(args.campaign_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_zip(
            args.campaign_id,
            strict=args.strict,
            require_real_audio=args.require_real_audio,
            require_manual_review=args.require_manual_review,
            require_fix_sprints_closed=args.require_fix_sprints_closed,
            require_signed=args.require_signed,
        )
        if args.report_out is not None:
            write_audio_campaign_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "governance":
        report = governance_store.refresh_governance_report(args.campaign_id)
        return {"ok": report.get("status") == "signed", "governance": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "analytics":
        analytics = governance_store.refresh_analytics(args.campaign_id)
        return {"ok": True, "analytics": analytics, "summary": analytics.get("summary", {}), "status": analytics.get("status")}
    if args.action == "archive":
        manifest = governance_store.export_archive(args.campaign_id)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "archive-zip":
        result = governance_store.build_archive_zip(args.campaign_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify-archive":
        report = governance_store.verify_archive(args.campaign_id, {"strict": args.strict, "require_signed": True, "require_verification_passed": True})
        if args.report_out is not None:
            write_audio_campaign_archive_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "remediation-plan":
        plan = remediation_store.refresh_plan(args.release_id)
        return {"ok": plan.get("status") != "blocked", "plan": plan, "summary": plan.get("summary", {}), "status": plan.get("status")}
    if args.action == "remediation-status":
        plan = remediation_store.refresh_plan(args.release_id)
        queue = remediation_store.build_action_queue(args.release_id)
        closeout = remediation_store.closeout_report(args.release_id)
        return {"ok": closeout.get("status") == "passed", "plan": plan, "queue": queue, "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")}
    if args.action == "remediation-run-safe":
        result = remediation_store.run_safe_actions(args.release_id, {"closed_by": args.closed_by})
        return {"ok": True, **result, "summary": result.get("closeout", {}).get("summary", {}), "status": result.get("closeout", {}).get("status")}
    if args.action == "remediation-closeout":
        closeout = remediation_store.closeout_report(args.release_id)
        return {"ok": closeout.get("status") == "passed", "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")}
    if args.action == "remediation-signoff":
        result = remediation_store.signoff(args.release_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("closeout", {}).get("summary", {}), "status": result.get("status")}
    if args.action == "remediation-export":
        result = remediation_store.export_package(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "remediation-zip":
        result = remediation_store.build_zip(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "remediation-verify":
        report = remediation_store.verify_zip(args.release_id, strict=args.strict, require_passed=args.require_passed, require_signed=args.require_signed)
        if args.report_out is not None:
            write_audio_campaign_remediation_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "change-request-create":
        cr = governance_store.create_change_request(args.campaign_id, {"created_by": args.created_by, "reason": args.reason, "risk": args.risk})
        return {"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}, "status": cr.get("status")}
    if args.action == "change-request-approve":
        cr = governance_store.approve_change_request(args.campaign_id, args.change_request_id, {"approved_by": args.approved_by, "reason": args.reason})
        return {"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}, "status": cr.get("status")}
    if args.action == "signoff-reset":
        result = governance_store.reset_signoff(args.campaign_id, args.change_request_id, {"reason": args.reason})
        return {"ok": True, **result, "summary": {"change_request_id": result.get("change_request", {}).get("change_request_id")}, "status": result.get("status")}
    raise ValueError("Unsupported audio-campaign command.")


def _print_audio_lab_result(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    status = result.get("status") or result.get("environment", {}).get("status") or result.get("summary", {}).get("status") or "unknown"
    print("MusicForge Audio Lab")
    print(f"status: {status}")
    if "environment" in result:
        summary = result["environment"].get("summary", {})
        print(f"renderer: {summary.get('renderer_status')}")
        print(f"real_audio_ready: {summary.get('real_audio_ready')}")
    if "smoke_run" in result:
        smoke = result["smoke_run"]
        print(f"smoke_run: {smoke.get('smoke_run_id')}")
    if "session" in result:
        session = result["session"]
        print(f"session: {session.get('session_id')}")
    if "comparison" in result:
        comparison = result["comparison"]
        print(f"comparison: {comparison.get('comparison_id')}")


def _print_audio_fix_sprint_result(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    status = result.get("status") or result.get("summary", {}).get("status") or "unknown"
    print("MusicForge Audio Fix Sprint")
    print(f"status: {status}")
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    if summary:
        details = []
        for key in ("issue_count", "candidate_count", "selected_count", "resolved_count", "manual_recheck_count", "test_fake_count"):
            if key in summary:
                details.append(f"{key}={summary.get(key)}")
        if details:
            print("summary: " + " ".join(details))
    if "sprint" in result:
        sprint = result["sprint"]
        print(f"sprint: {sprint.get('fix_sprint_id')} stale={sprint.get('stale', False)}")
    if "closeout" in result:
        closeout = result["closeout"]
        blockers = closeout.get("blockers") or []
        print(f"closeout: {closeout.get('status')} blockers={','.join(blockers) if blockers else '-'}")


def _print_audio_campaign_result(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    status = result.get("status") or result.get("summary", {}).get("status") or "unknown"
    print("MusicForge Audio Campaign")
    print(f"status: {status}")
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    details = []
    for key in ("case_count", "manual_review_count", "real_audio_count", "test_fake_count", "open_fix_sprint_count"):
        if key in summary:
            details.append(f"{key}={summary.get(key)}")
    if details:
        print("summary: " + " ".join(details))
    if "campaign" in result:
        campaign = result["campaign"]
        print(f"campaign: {campaign.get('campaign_id')} {campaign.get('name')}")
    if "verification" in result:
        verification = result["verification"]
        print(f"verification: {verification.get('status')} blockers={verification.get('blockers') or []}")


def _main() -> None:
    raw_args = sys.argv[1:]
    if raw_args and raw_args[0] == "serve":
        parser = build_serve_parser()
        args = parser.parse_args(raw_args[1:])
        from song_agent.server import serve

        auth_config = build_auth_config(args.host, args.access_token, os.environ)
        serve(args.host, args.port, auth_config=auth_config)
        return

    if raw_args and raw_args[0] == "generate":
        parser = build_generate_parser()
        args = parser.parse_args(raw_args[1:])
    elif raw_args and raw_args[0] == "doctor":
        parser = build_doctor_parser()
        args = parser.parse_args(raw_args[1:])
        run_doctor(provider_test=args.provider_test)
        return
    elif raw_args and raw_args[0] == "ga-check":
        from song_agent.ga_readiness import build_ga_readiness_report, write_ga_readiness_report

        parser = build_ga_check_parser()
        args = parser.parse_args(raw_args[1:])
        report = build_ga_readiness_report(
            strict=args.strict,
            allow_dirty=args.allow_dirty,
            require_manual_acceptance=args.require_manual_acceptance,
            require_audio=args.require_audio,
            require_audio_campaign=bool(args.audio_campaign_id),
            audio_campaign_id=args.audio_campaign_id,
            audio_campaign_archive_zip_path=args.audio_campaign_archive,
            audio_campaign_archive_verification_report_path=args.audio_campaign_archive_verification_report,
            require_audio_campaign_remediation=args.require_audio_campaign_remediation,
            audio_campaign_remediation_zip_path=args.audio_campaign_remediation,
            audio_campaign_remediation_verification_report_path=args.audio_campaign_remediation_verification_report,
            require_final_readiness=args.require_final_readiness,
            final_handoff_verification_report_path=args.final_handoff_verification_report,
            release_check_latest_report_path=args.release_check_latest_report,
            release_check_ga_report_path=args.release_check_ga_report,
            run_release_checks=args.run_release_checks,
            skip_tests=args.skip_tests,
        )
        if args.report_out is not None:
            write_ga_readiness_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_ga_readiness_report(report)
        if report.get("status") == "blocked":
            raise SystemExit(1)
        return
    elif raw_args and raw_args[0] == "verify-ga-readiness-report":
        from song_agent.ga_readiness_verifier import verify_ga_readiness_report, write_ga_readiness_verification_report

        parser = build_verify_ga_readiness_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_ga_readiness_report(
            args.report_path,
            strict=args.strict,
            require_ready=args.require_ready,
            require_manual_acceptance=args.require_manual_acceptance,
            require_audio_campaign=args.require_audio_campaign,
            require_audio_campaign_remediation=args.require_audio_campaign_remediation,
            require_final_readiness=args.require_final_readiness,
            manual_acceptance_report_path=args.manual_acceptance_report,
            audio_campaign_archive_path=args.audio_campaign_archive,
            audio_campaign_archive_verification_report_path=args.audio_campaign_archive_verification_report,
            audio_campaign_remediation_path=args.audio_campaign_remediation,
            audio_campaign_remediation_verification_report_path=args.audio_campaign_remediation_verification_report,
            final_handoff_package_path=args.final_handoff_package,
            final_handoff_verification_report_path=args.final_handoff_verification_report,
        )
        if args.report_out is not None:
            write_ga_readiness_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"MusicForge GA readiness verification: {report.get('status')}")
            for check in report.get("checks", []):
                marker = "ok" if check.get("status") == "passed" else check.get("status")
                print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
        if report.get("status") == "failed":
            raise SystemExit(1)
        return
    elif raw_args and raw_args[0] == "maintenance":
        parser = build_maintenance_parser()
        args = parser.parse_args(raw_args[1:])
        result = _run_maintenance_command(args)
        _print_maintenance_result(result, json_output=bool(getattr(args, "json", False)))
        status = str(result.get("status") or result.get("report", {}).get("status") or result.get("verification", {}).get("status") or "")
        if status in {"blocked", "failed"}:
            raise SystemExit(1)
        return
    elif raw_args and raw_args[0] == "audio-lab":
        parser = build_audio_lab_parser()
        args = parser.parse_args(raw_args[1:])
        result = _run_audio_lab_command(args)
        json_output = bool(getattr(args, "json", False))
        _print_audio_lab_result(result, json_output=json_output)
        status = str(result.get("status") or result.get("summary", {}).get("status") or "")
        if result.get("ok") is False or status in {"failed", "blocked"}:
            raise SystemExit(1)
        return
    elif raw_args and raw_args[0] == "audio-fix-sprint":
        parser = build_audio_fix_sprint_parser()
        args = parser.parse_args(raw_args[1:])
        result = _run_audio_fix_sprint_command(args)
        json_output = bool(getattr(args, "json", False))
        _print_audio_fix_sprint_result(result, json_output=json_output)
        status = str(result.get("status") or result.get("summary", {}).get("status") or "")
        if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
            raise SystemExit(1)
        return
    elif raw_args and raw_args[0] == "audio-campaign":
        parser = build_audio_campaign_parser()
        args = parser.parse_args(raw_args[1:])
        result = _run_audio_campaign_command(args)
        json_output = bool(getattr(args, "json", False))
        _print_audio_campaign_result(result, json_output=json_output)
        status = str(result.get("status") or result.get("summary", {}).get("status") or "")
        if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
            raise SystemExit(1)
        return
    elif raw_args and raw_args[0] == "verify-audio-campaign-package":
        from song_agent.audio_campaign_verifier import audio_campaign_verification_exit_code, verify_audio_campaign_package, write_audio_campaign_verification_report

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
    elif raw_args and raw_args[0] == "verify-audio-campaign-archive-package":
        from song_agent.audio_campaign_archive_verifier import (
            audio_campaign_archive_verification_exit_code,
            verify_audio_campaign_archive_package,
            write_audio_campaign_archive_verification_report,
        )

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
    elif raw_args and raw_args[0] == "verify-audio-campaign-remediation-package":
        from song_agent.audio_campaign_remediation_verifier import (
            audio_campaign_remediation_verification_exit_code,
            verify_audio_campaign_remediation_package,
            write_audio_campaign_remediation_verification_report,
        )

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
    elif raw_args and raw_args[0] == "verify-maintenance-backup":
        from song_agent.lts_backup_verifier import (
            maintenance_backup_verification_exit_code,
            print_maintenance_backup_verification_report,
            verify_maintenance_backup_zip,
            write_maintenance_backup_verification_report,
        )

        parser = build_verify_maintenance_backup_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_maintenance_backup_zip(
            args.zip_path,
            strict=args.strict,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_maintenance_backup_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_maintenance_backup_verification_report(report)
        raise SystemExit(maintenance_backup_verification_exit_code(report))
    elif raw_args and raw_args[0] == "release-check":
        from song_agent.release_check_matrix import release_check_definitions_as_dicts, select_check_definitions
        from song_agent.release_check_runner import print_release_check_report, run_release_check_matrix, write_json_report, write_timing_report

        parser = build_release_check_parser()
        args = parser.parse_args(raw_args[1:])
        selected = select_check_definitions(
            profile=args.profile,
            groups=args.group,
            since=args.since,
            only=args.only,
            run_tests=not args.skip_tests,
        )
        if args.list:
            rows = release_check_definitions_as_dicts(selected)
            if args.json:
                print(json.dumps({"checks": rows}, ensure_ascii=False, indent=2))
            else:
                for item in rows:
                    print(f"{item['check_id']}\t{item['group']}\t{item.get('version') or '-'}\t{item['name']}")
            return

        def _progress(definition: Any) -> None:
            print(f"[release-check] running {definition.check_id} ...", file=sys.stderr, flush=True)

        report = run_release_check_matrix(
            profile=args.profile,
            groups=args.group,
            since=args.since,
            only=args.only,
            run_tests=not args.skip_tests,
            fail_fast=args.fail_fast,
            timeout_seconds=args.timeout_seconds,
            progress=None if args.json else _progress,
        )
        if args.report_out is not None:
            write_json_report(report, args.report_out)
        if args.timing_out is not None:
            write_timing_report(report, args.timing_out)
        if args.json:
            print(json.dumps(report.to_json_report(), ensure_ascii=False, indent=2))
        else:
            print_release_check_report(report)
        if not report.ok:
            raise SystemExit(1)
        return
    elif raw_args and raw_args[0] == "verify-release":
        from song_agent.release_verifier import release_verification_exit_code, print_verification_report, verify_release_zip, write_verification_report

        parser = build_verify_release_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_zip(
            args.zip_path,
            strict=args.strict,
            require_audio=args.require_audio,
            require_human_review=args.require_human_review,
            require_audio_revisions=args.require_audio_revisions,
            require_stems=args.require_stems,
            require_mastering=args.require_mastering,
            require_encoded_audio=args.require_encoded_audio,
            require_encoded_audio_review=args.require_encoded_audio_review,
            require_format_decision=args.require_format_decision,
            require_rights_clearance=args.require_rights_clearance,
            required_audio_format_profiles=[item.strip() for item in str(args.require_audio_formats or "").split(",") if item.strip()],
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_verification_report(report)
        raise SystemExit(release_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-distribution-package":
        from song_agent.distribution_verifier import (
            distribution_verification_exit_code,
            print_distribution_verification_report,
            verify_distribution_package,
            write_distribution_verification_report,
        )

        parser = build_verify_distribution_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_distribution_package(
            args.zip_path,
            strict=args.strict,
            require_audio=args.require_audio,
            require_artwork=args.require_artwork,
            require_encoded_audio=args.require_encoded_audio,
            require_encoded_audio_review=args.require_encoded_audio_review,
            require_format_decision=args.require_format_decision,
            require_rights_clearance=args.require_rights_clearance,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_distribution_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_distribution_verification_report(report)
        raise SystemExit(distribution_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-submission-package":
        from song_agent.submission_verifier import (
            print_submission_verification_report,
            submission_verification_exit_code,
            verify_submission_package,
            write_submission_verification_report,
        )

        parser = build_verify_submission_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_submission_package(
            args.zip_path,
            strict=args.strict,
            require_submitted=args.require_submitted,
            require_accepted=args.require_accepted,
            require_rights_clearance=args.require_rights_clearance,
            deep=args.deep,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_submission_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_submission_verification_report(report)
        raise SystemExit(submission_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-submission-evidence-package":
        from song_agent.submission_evidence_verifier import (
            print_submission_evidence_verification_report,
            submission_evidence_verification_exit_code,
            verify_submission_evidence_package,
            write_submission_evidence_verification_report,
        )

        parser = build_verify_submission_evidence_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_submission_evidence_package(
            args.zip_path,
            strict=args.strict,
            deep=args.deep,
            require_submitted=args.require_submitted,
            require_accepted=args.require_accepted,
            require_rights_clearance=args.require_rights_clearance,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_submission_evidence_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_submission_evidence_verification_report(report)
        raise SystemExit(submission_evidence_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-operations-package":
        from song_agent.release_operations_verifier import (
            print_release_operations_verification_report,
            release_operations_verification_exit_code,
            verify_release_operations_package,
        )

        parser = build_verify_release_operations_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_operations_package(
            args.zip_path,
            strict=args.strict,
            require_accepted=args.require_accepted,
            require_submission_evidence=args.require_submission_evidence,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_json(args.report_out, report)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_operations_verification_report(report)
        raise SystemExit(release_operations_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-operations-runbook-package":
        from song_agent.release_operations_runbook_verifier import (
            print_release_operations_runbook_verification_report,
            release_operations_runbook_verification_exit_code,
            verify_release_operations_runbook_package,
            write_release_operations_runbook_verification_report,
        )

        parser = build_verify_release_operations_runbook_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_operations_runbook_package(
            args.zip_path,
            strict=args.strict,
            require_completed=args.require_completed,
            require_current=args.require_current,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_operations_runbook_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_operations_runbook_verification_report(report)
        raise SystemExit(release_operations_runbook_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-operations-archive-package":
        from song_agent.release_operations_archive_verifier import (
            print_release_operations_archive_verification_report,
            release_operations_archive_verification_exit_code,
            verify_release_operations_archive_package,
            write_release_operations_archive_verification_report,
        )

        parser = build_verify_release_operations_archive_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_operations_archive_package(
            args.zip_path,
            strict=args.strict,
            require_signed=args.require_signed,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_operations_archive_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_operations_archive_verification_report(report)
        raise SystemExit(release_operations_archive_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-operations-audit-package":
        from song_agent.release_operations_audit_verifier import (
            print_release_operations_audit_verification_report,
            release_operations_audit_verification_exit_code,
            verify_release_operations_audit_package,
            write_release_operations_audit_verification_report,
        )

        parser = build_verify_release_operations_audit_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_operations_audit_package(
            args.zip_path,
            strict=args.strict,
            require_current=args.require_current,
            require_signed=args.require_signed,
            require_archive=args.require_archive,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_operations_audit_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_operations_audit_verification_report(report)
        raise SystemExit(release_operations_audit_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-operations-reviewer-pack":
        from song_agent.release_operations_reviewer_pack_verifier import (
            print_release_operations_reviewer_pack_verification_report,
            release_operations_reviewer_pack_verification_exit_code,
            verify_release_operations_reviewer_pack,
            write_release_operations_reviewer_pack_verification_report,
        )

        parser = build_verify_release_operations_reviewer_pack_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_operations_reviewer_pack(
            args.zip_path,
            strict=args.strict,
            require_audit=args.require_audit,
            require_signed=args.require_signed,
            require_archive=args.require_archive,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_operations_reviewer_pack_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_operations_reviewer_pack_verification_report(report)
        raise SystemExit(release_operations_reviewer_pack_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-audit-package":
        from song_agent.release_portfolio_audit_verifier import (
            print_release_portfolio_audit_verification_report,
            release_portfolio_audit_verification_exit_code,
            verify_release_portfolio_audit_package,
            write_release_portfolio_audit_verification_report,
        )

        parser = build_verify_release_portfolio_audit_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_audit_package(
            args.zip_path,
            strict=args.strict,
            require_reviewer_packs=args.require_reviewer_packs,
            require_audit=args.require_audit,
            require_archive=args.require_archive,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_audit_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_audit_verification_report(report)
        raise SystemExit(release_portfolio_audit_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-package":
        from song_agent.release_portfolio_governance_verifier import (
            print_release_portfolio_governance_verification_report,
            release_portfolio_governance_verification_exit_code,
            verify_release_portfolio_governance_package,
            write_release_portfolio_governance_verification_report,
        )

        parser = build_verify_release_portfolio_governance_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_package(
            args.zip_path,
            strict=args.strict,
            require_manual_actions=args.require_manual_actions,
            require_no_blocked=args.require_no_blocked,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_verification_report(report)
        raise SystemExit(release_portfolio_governance_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-archive-package":
        from song_agent.release_portfolio_governance_archive_verifier import (
            print_release_portfolio_governance_archive_verification_report,
            release_portfolio_governance_archive_verification_exit_code,
            verify_release_portfolio_governance_archive_package,
            write_release_portfolio_governance_archive_verification_report,
        )

        parser = build_verify_release_portfolio_governance_archive_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_archive_package(
            args.zip_path,
            strict=args.strict,
            require_signed=args.require_signed,
            require_no_force=args.require_no_force,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_archive_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_archive_verification_report(report)
        raise SystemExit(release_portfolio_governance_archive_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-audit-package":
        from song_agent.release_portfolio_governance_audit_verifier import (
            print_release_portfolio_governance_audit_verification_report,
            release_portfolio_governance_audit_verification_exit_code,
            verify_release_portfolio_governance_audit_package,
            write_release_portfolio_governance_audit_verification_report,
        )

        parser = build_verify_release_portfolio_governance_audit_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_audit_package(
            args.zip_path,
            strict=args.strict,
            require_signed=args.require_signed,
            require_archives=args.require_archives,
            require_no_force=args.require_no_force,
            require_reset_cr_causality=args.require_reset_cr_causality,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_audit_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_audit_verification_report(report)
        raise SystemExit(release_portfolio_governance_audit_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-reviewer-pack":
        from song_agent.release_portfolio_governance_reviewer_pack_verifier import (
            print_release_portfolio_governance_reviewer_pack_verification_report,
            release_portfolio_governance_reviewer_pack_verification_exit_code,
            verify_release_portfolio_governance_reviewer_pack,
            write_release_portfolio_governance_reviewer_pack_verification_report,
        )

        parser = build_verify_release_portfolio_governance_reviewer_pack_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_reviewer_pack(
            args.zip_path,
            strict=args.strict,
            require_audit=args.require_audit,
            require_signed=args.require_signed,
            require_archives=args.require_archives,
            require_no_force=args.require_no_force,
            require_reset_cr_causality=args.require_reset_cr_causality,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_reviewer_pack_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_reviewer_pack_verification_report(report)
        raise SystemExit(release_portfolio_governance_reviewer_pack_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-final-board":
        from song_agent.release_portfolio_governance_final_board_verifier import (
            print_release_portfolio_governance_final_board_verification_report,
            release_portfolio_governance_final_board_verification_exit_code,
            verify_release_portfolio_governance_final_board_package,
            write_release_portfolio_governance_final_board_verification_report,
        )

        parser = build_verify_release_portfolio_governance_final_board_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_final_board_package(
            args.zip_path,
            strict=args.strict,
            require_signed=args.require_signed,
            require_reviewer_pack=args.require_reviewer_pack,
            require_audit=args.require_audit,
            require_archives=args.require_archives,
            require_reviewer_response=args.require_reviewer_response,
            require_no_force=args.require_no_force,
            require_reset_cr_causality=args.require_reset_cr_causality,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_final_board_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_final_board_verification_report(report)
        raise SystemExit(release_portfolio_governance_final_board_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-evidence-vault":
        from song_agent.release_portfolio_governance_evidence_vault_verifier import (
            print_release_portfolio_governance_evidence_vault_verification_report,
            release_portfolio_governance_evidence_vault_verification_exit_code,
            verify_release_portfolio_governance_evidence_vault_package,
            write_release_portfolio_governance_evidence_vault_verification_report,
        )

        parser = build_verify_release_portfolio_governance_evidence_vault_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_evidence_vault_package(
            args.zip_path,
            strict=args.strict,
            deep=args.deep,
            require_final_board=args.require_final_board,
            require_reviewer_pack=args.require_reviewer_pack,
            require_audit=args.require_audit,
            require_archives=args.require_archives,
            require_queue_packages=args.require_queue_packages,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_evidence_vault_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_evidence_vault_verification_report(report)
        raise SystemExit(release_portfolio_governance_evidence_vault_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-attestation":
        from song_agent.release_portfolio_governance_attestation_verifier import (
            print_release_portfolio_governance_attestation_verification_report,
            release_portfolio_governance_attestation_verification_exit_code,
            verify_release_portfolio_governance_attestation,
            write_release_portfolio_governance_attestation_verification_report,
        )

        parser = build_verify_release_portfolio_governance_attestation_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_attestation(
            args.zip_path,
            strict=args.strict,
            require_vault=args.require_vault,
            require_final_board=args.require_final_board,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_attestation_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_verification_report(report)
        raise SystemExit(release_portfolio_governance_attestation_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-attestation-registry":
        from song_agent.release_portfolio_governance_attestation_registry_verifier import (
            print_release_portfolio_governance_attestation_registry_verification_report,
            release_portfolio_governance_attestation_registry_verification_exit_code,
            verify_release_portfolio_governance_attestation_registry,
            write_release_portfolio_governance_attestation_registry_verification_report,
        )

        parser = build_verify_release_portfolio_governance_attestation_registry_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_attestation_registry(
            args.zip_path,
            strict=args.strict,
            require_current=args.require_current,
            require_published=args.require_published,
            require_no_revoked_current=args.require_no_revoked_current,
            require_accepted_evidence=args.require_accepted_evidence,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_attestation_registry_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_registry_verification_report(report)
        raise SystemExit(release_portfolio_governance_attestation_registry_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-attestation-portal":
        from song_agent.release_portfolio_governance_attestation_portal_verifier import (
            print_release_portfolio_governance_attestation_portal_verification_report,
            release_portfolio_governance_attestation_portal_verification_exit_code,
            verify_release_portfolio_governance_attestation_portal,
            write_release_portfolio_governance_attestation_portal_verification_report,
        )

        parser = build_verify_release_portfolio_governance_attestation_portal_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_attestation_portal(
            args.zip_path,
            strict=args.strict,
            require_current=args.require_current,
            require_registry=args.require_registry,
            require_attestation=args.require_attestation,
            require_accepted_evidence=args.require_accepted_evidence,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_attestation_portal_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_portal_verification_report(report)
        raise SystemExit(release_portfolio_governance_attestation_portal_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-attestation-portal-review-pack":
        from song_agent.release_portfolio_governance_attestation_portal_review_verifier import (
            print_release_portfolio_governance_attestation_portal_review_pack_verification_report,
            release_portfolio_governance_attestation_portal_review_verification_exit_code,
            verify_release_portfolio_governance_attestation_portal_review_pack,
            write_release_portfolio_governance_attestation_portal_review_pack_verification_report,
        )

        parser = build_verify_release_portfolio_governance_attestation_portal_review_pack_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_attestation_portal_review_pack(
            args.zip_path,
            strict=args.strict,
            require_current=args.require_current,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_attestation_portal_review_pack_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_portal_review_pack_verification_report(report)
        raise SystemExit(release_portfolio_governance_attestation_portal_review_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-attestation-portal-response":
        from song_agent.release_portfolio_governance_attestation_portal_review_verifier import (
            print_release_portfolio_governance_attestation_portal_response_verification_report,
            release_portfolio_governance_attestation_portal_review_verification_exit_code,
            verify_release_portfolio_governance_attestation_portal_response,
            write_release_portfolio_governance_attestation_portal_response_verification_report,
        )

        parser = build_verify_release_portfolio_governance_attestation_portal_response_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_attestation_portal_response(
            args.zip_path,
            strict=args.strict,
            require_current=args.require_current,
            require_pack=args.require_pack,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_attestation_portal_response_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_portal_response_verification_report(report)
        raise SystemExit(release_portfolio_governance_attestation_portal_review_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-attestation-accepted-evidence":
        from song_agent.release_portfolio_governance_attestation_accepted_evidence_verifier import (
            print_release_portfolio_governance_attestation_accepted_evidence_verification_report,
            release_portfolio_governance_attestation_accepted_evidence_verification_exit_code,
            verify_release_portfolio_governance_attestation_accepted_evidence,
            write_release_portfolio_governance_attestation_accepted_evidence_verification_report,
        )

        parser = build_verify_release_portfolio_governance_attestation_accepted_evidence_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_attestation_accepted_evidence(
            args.zip_path,
            strict=args.strict,
            require_current=args.require_current,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_attestation_accepted_evidence_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_accepted_evidence_verification_report(report)
        raise SystemExit(release_portfolio_governance_attestation_accepted_evidence_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-attestation-transparency":
        from song_agent.release_portfolio_governance_attestation_transparency_verifier import (
            print_release_portfolio_governance_attestation_transparency_verification_report,
            release_portfolio_governance_attestation_transparency_verification_exit_code,
            verify_release_portfolio_governance_attestation_transparency,
            write_release_portfolio_governance_attestation_transparency_verification_report,
        )

        parser = build_verify_release_portfolio_governance_attestation_transparency_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_attestation_transparency(
            args.zip_path,
            strict=args.strict,
            require_current=args.require_current,
            require_accepted_evidence=args.require_accepted_evidence,
            require_no_revoked_current=args.require_no_revoked_current,
            require_contiguous_chain=args.require_contiguous_chain,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_attestation_transparency_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_transparency_verification_report(report)
        raise SystemExit(release_portfolio_governance_attestation_transparency_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-release-portfolio-governance-attestation-transparency-acknowledgement":
        from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement_verifier import (
            print_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report,
            release_portfolio_governance_attestation_transparency_acknowledgement_verification_exit_code,
            verify_release_portfolio_governance_attestation_transparency_acknowledgement_package,
            write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report,
        )

        parser = build_verify_release_portfolio_governance_attestation_transparency_acknowledgement_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(
            args.zip_path,
            strict=args.strict,
            require_pack=args.require_pack,
            require_response=args.require_response,
            require_accepted=args.require_accepted,
            require_transparency=args.require_transparency,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report)
        raise SystemExit(release_portfolio_governance_attestation_transparency_acknowledgement_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-public-trust-center-package":
        from song_agent.public_trust_center_verifier import (
            print_public_trust_center_verification_report,
            public_trust_center_verification_exit_code,
            verify_public_trust_center_package,
            write_public_trust_center_verification_report,
        )

        parser = build_verify_public_trust_center_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_public_trust_center_package(
            args.zip_path,
            strict=args.strict,
            require_release_readiness=args.require_release_readiness,
            require_public_attestation=args.require_public_attestation,
            require_registry_current=args.require_registry_current,
            require_portal_current=args.require_portal_current,
            require_transparency_current=args.require_transparency_current,
            require_acknowledgement_current=args.require_acknowledgement_current,
            require_delivery_readiness=args.require_delivery_readiness,
            require_distribution_ready=args.require_distribution_ready,
            require_submission_accepted=args.require_submission_accepted,
            require_submission_evidence=args.require_submission_evidence,
            require_operations_signed=args.require_operations_signed,
            require_operations_audit=args.require_operations_audit,
            require_operations_reviewer_pack=args.require_operations_reviewer_pack,
            require_acceptance_board_signoff=args.require_acceptance_board_signoff,
            delivery_anchor_path=args.delivery_anchor,
            anchor_registry_path=args.anchor_registry,
            anchor_transparency_path=args.anchor_transparency,
            anchor_checkpoint_path=args.anchor_checkpoint,
            acceptance_board_signoff_archive_path=args.acceptance_board_signoff_archive,
            acceptance_board_path=args.acceptance_board,
            acceptance_board_verification_report_path=args.acceptance_board_verification_report,
            distribution_kit_path=args.distribution_kit,
            accepted_evidence_dir=args.accepted_evidence_dir,
            require_anchor_registry_current=args.require_anchor_registry_current,
            require_anchor_published=args.require_anchor_published,
            require_anchor_not_revoked=args.require_anchor_not_revoked,
            require_anchor_transparency_current=args.require_anchor_transparency_current,
            require_anchor_checkpoint=args.require_anchor_checkpoint,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_public_trust_center_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_public_trust_center_verification_report(report)
        raise SystemExit(public_trust_center_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-public-trust-center-anchor-registry-package":
        from song_agent.public_trust_center_anchor_registry_verifier import (
            print_public_trust_center_anchor_registry_verification_report,
            public_trust_center_anchor_registry_verification_exit_code,
            verify_public_trust_center_anchor_registry_package,
            write_public_trust_center_anchor_registry_verification_report,
        )

        parser = build_verify_public_trust_center_anchor_registry_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_public_trust_center_anchor_registry_package(
            args.zip_path,
            strict=args.strict,
            require_current=args.require_current,
            require_anchor_published=args.require_anchor_published,
            require_anchor_not_revoked=args.require_anchor_not_revoked,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_public_trust_center_anchor_registry_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_public_trust_center_anchor_registry_verification_report(report)
        raise SystemExit(public_trust_center_anchor_registry_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-public-trust-center-anchor-transparency-package":
        from song_agent.public_trust_center_anchor_transparency_verifier import (
            print_public_trust_center_anchor_transparency_verification_report,
            public_trust_center_anchor_transparency_verification_exit_code,
            verify_public_trust_center_anchor_transparency_package,
            write_public_trust_center_anchor_transparency_verification_report,
        )

        parser = build_verify_public_trust_center_anchor_transparency_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_public_trust_center_anchor_transparency_package(
            args.zip_path,
            strict=args.strict,
            checkpoint_path=args.checkpoint,
            anchor_registry_path=args.anchor_registry,
            require_current_checkpoint=args.require_current_checkpoint,
            require_published_anchor=args.require_published_anchor,
            require_not_revoked=args.require_not_revoked,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_public_trust_center_anchor_transparency_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_public_trust_center_anchor_transparency_verification_report(report)
        raise SystemExit(public_trust_center_anchor_transparency_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-public-trust-center-distribution-kit-package":
        from song_agent.public_trust_center_distribution_kit_verifier import (
            print_public_trust_center_distribution_kit_verification_report,
            public_trust_center_distribution_kit_verification_exit_code,
            verify_public_trust_center_distribution_kit_package,
            write_public_trust_center_distribution_kit_verification_report,
        )

        parser = build_verify_public_trust_center_distribution_kit_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_public_trust_center_distribution_kit_package(
            args.zip_path,
            strict=args.strict,
            deep=args.deep,
            require_current=args.require_current,
            require_delivery_readiness=args.require_delivery_readiness,
            require_anchor_registry_current=args.require_anchor_registry_current,
            require_anchor_published=args.require_anchor_published,
            require_anchor_not_revoked=args.require_anchor_not_revoked,
            require_anchor_transparency_current=args.require_anchor_transparency_current,
            require_anchor_checkpoint=args.require_anchor_checkpoint,
            require_acceptance_board_signoff=args.require_acceptance_board_signoff,
            acceptance_board_signoff_archive_path=args.acceptance_board_signoff_archive,
            acceptance_board_path=args.acceptance_board,
            acceptance_board_verification_report_path=args.acceptance_board_verification_report,
            accepted_evidence_dir=args.accepted_evidence_dir,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_public_trust_center_distribution_kit_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_public_trust_center_distribution_kit_verification_report(report)
        raise SystemExit(public_trust_center_distribution_kit_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-public-trust-center-distribution-kit-accepted-evidence-package":
        from song_agent.public_trust_center_distribution_kit_acceptance_verifier import (
            print_public_trust_center_distribution_kit_accepted_evidence_verification_report,
            public_trust_center_distribution_kit_accepted_evidence_verification_exit_code,
            verify_public_trust_center_distribution_kit_accepted_evidence_package,
            write_public_trust_center_distribution_kit_accepted_evidence_verification_report,
        )

        parser = build_verify_public_trust_center_distribution_kit_accepted_evidence_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_public_trust_center_distribution_kit_accepted_evidence_package(
            args.zip_path,
            strict=args.strict,
            require_current=args.require_current,
            distribution_kit_path=args.distribution_kit,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_public_trust_center_distribution_kit_accepted_evidence_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_public_trust_center_distribution_kit_accepted_evidence_verification_report(report)
        raise SystemExit(public_trust_center_distribution_kit_accepted_evidence_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-public-trust-center-acceptance-board-package":
        from song_agent.public_trust_center_acceptance_board_verifier import (
            print_public_trust_center_acceptance_board_verification_report,
            public_trust_center_acceptance_board_verification_exit_code,
            verify_public_trust_center_acceptance_board_package,
            write_public_trust_center_acceptance_board_verification_report,
        )

        parser = build_verify_public_trust_center_acceptance_board_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_public_trust_center_acceptance_board_package(
            args.zip_path,
            strict=args.strict,
            require_ready=args.require_ready,
            require_quorum=args.require_quorum,
            require_no_conflicts=args.require_no_conflicts,
            min_accepted_count=args.min_accepted_count,
            min_accepted_organizations=args.min_accepted_organizations,
            required_roles=args.required_roles,
            distribution_kit_path=args.distribution_kit,
            accepted_evidence_dir=args.accepted_evidence_dir,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_public_trust_center_acceptance_board_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_public_trust_center_acceptance_board_verification_report(report)
        raise SystemExit(public_trust_center_acceptance_board_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-public-trust-center-acceptance-board-signoff-archive-package":
        from song_agent.public_trust_center_acceptance_board_signoff_verifier import (
            print_public_trust_center_acceptance_board_signoff_archive_verification_report,
            public_trust_center_acceptance_board_signoff_archive_verification_exit_code,
            verify_public_trust_center_acceptance_board_signoff_archive_package,
            write_public_trust_center_acceptance_board_signoff_archive_verification_report,
        )

        parser = build_verify_public_trust_center_acceptance_board_signoff_archive_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_public_trust_center_acceptance_board_signoff_archive_package(
            args.zip_path,
            strict=args.strict,
            require_signed=args.require_signed,
            require_current=args.require_current,
            require_ready=args.require_ready,
            board_zip_path=args.board_zip,
            board_verification_report_path=args.board_verification_report,
            distribution_kit_path=args.distribution_kit,
            accepted_evidence_dir=args.accepted_evidence_dir,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_public_trust_center_acceptance_board_signoff_archive_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_public_trust_center_acceptance_board_signoff_archive_verification_report(report)
        raise SystemExit(public_trust_center_acceptance_board_signoff_archive_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-public-trust-center-publication-package":
        from song_agent.public_trust_center_publication_verifier import (
            print_public_trust_center_publication_verification_report,
            public_trust_center_publication_verification_exit_code,
            verify_public_trust_center_publication_package,
            write_public_trust_center_publication_verification_report,
        )

        parser = build_verify_public_trust_center_publication_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_public_trust_center_publication_package(
            args.zip_path,
            strict=args.strict,
            deep=args.deep,
            require_ready=args.require_ready,
            require_acceptance_board_signoff=args.require_acceptance_board_signoff,
            require_anchor_current=args.require_anchor_current,
            require_no_revoked=args.require_no_revoked,
            publication_channel_state_path=args.publication_channel_state,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_public_trust_center_publication_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_public_trust_center_publication_verification_report(report)
        raise SystemExit(public_trust_center_publication_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-public-trust-center-publication-mirror":
        from song_agent.public_trust_center_publication_verifier import (
            print_public_trust_center_publication_verification_report,
            public_trust_center_publication_verification_exit_code,
            verify_public_trust_center_publication_mirror,
            write_public_trust_center_publication_verification_report,
        )

        parser = build_verify_public_trust_center_publication_mirror_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_public_trust_center_publication_mirror(
            args.mirror_dir,
            strict=args.strict,
            require_ready=args.require_ready,
            require_acceptance_board_signoff=args.require_acceptance_board_signoff,
            require_anchor_current=args.require_anchor_current,
            require_no_revoked=args.require_no_revoked,
            publication_channel_state_path=args.publication_channel_state,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_public_trust_center_publication_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_public_trust_center_publication_verification_report(report)
        raise SystemExit(public_trust_center_publication_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-public-trust-center-publication-monitoring-package":
        from song_agent.public_trust_center_publication_monitoring_verifier import (
            print_public_trust_center_publication_monitoring_verification_report,
            public_trust_center_publication_monitoring_verification_exit_code,
            verify_public_trust_center_publication_monitoring_package,
            write_public_trust_center_publication_monitoring_verification_report,
        )

        parser = build_verify_public_trust_center_publication_monitoring_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_public_trust_center_publication_monitoring_package(
            args.zip_path,
            strict=args.strict,
            require_current=args.require_current,
            require_no_revoked=args.require_no_revoked,
            require_ready=args.require_ready,
            require_no_drift=args.require_no_drift,
            require_no_open_critical_incidents=args.require_no_open_critical_incidents,
            allow_waived_incidents=args.allow_waived_incidents,
            publication_channel_state_path=args.publication_channel_state,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_public_trust_center_publication_monitoring_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_public_trust_center_publication_monitoring_verification_report(report)
        raise SystemExit(public_trust_center_publication_monitoring_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-trust-operations-hub-package":
        from song_agent.trust_operations_hub_verifier import (
            print_trust_operations_hub_verification_report,
            trust_operations_hub_verification_exit_code,
            verify_trust_operations_hub_package,
            write_trust_operations_hub_verification_report,
        )

        parser = build_verify_trust_operations_hub_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_trust_operations_hub_package(
            args.zip_path,
            strict=args.strict,
            require_ready=args.require_ready,
            require_signed=args.require_signed,
            require_current=args.require_current,
            require_no_critical_blockers=args.require_no_critical_blockers,
            require_publication_monitoring_clean=args.require_publication_monitoring_clean,
            require_delivery_ready=args.require_delivery_ready,
            require_incident_closeout=args.require_incident_closeout,
            require_incident_regression_guards=args.require_incident_regression_guards,
            require_trust_controls=args.require_trust_controls,
            require_trust_control_signoff=args.require_trust_control_signoff,
            require_continuous_assurance=args.require_continuous_assurance,
            publication_channel_state_path=args.publication_channel_state,
            public_trust_center_verification_path=args.public_trust_center_verification,
            publication_monitoring_verification_path=args.publication_monitoring_verification,
            release_verification_paths=args.release_verification,
            distribution_verification_paths=args.distribution_verification,
            submission_verification_paths=args.submission_verification,
            submission_evidence_verification_paths=args.submission_evidence_verification,
            release_operations_verification_paths=args.release_operations_verification,
            hub_signoff_path=args.hub_signoff,
            hub_verification_report_path=args.hub_verification_report,
            incident_board_package_path=args.incident_board_package,
            incident_board_verification_report_path=args.incident_board_verification_report,
            incident_knowledge_package_path=args.incident_knowledge_package,
            incident_knowledge_verification_report_path=args.incident_knowledge_verification_report,
            trust_control_package_path=args.trust_control_package,
            trust_control_verification_report_path=args.trust_control_verification_report,
            trust_control_signoff_archive_path=args.trust_control_signoff_archive,
            trust_control_signoff_verification_report_path=args.trust_control_signoff_verification_report,
            continuous_assurance_archive_path=args.continuous_assurance_archive,
            continuous_assurance_verification_report_path=args.continuous_assurance_verification_report,
            require_assurance_watch_clear=args.require_assurance_watch_clear,
            assurance_watch_package_path=args.assurance_watch_package,
            assurance_watch_verification_report_path=args.assurance_watch_verification_report,
            require_assurance_watch_signoff=args.require_assurance_watch_signoff,
            assurance_watch_signoff_archive_path=args.assurance_watch_signoff_archive,
            assurance_watch_signoff_verification_report_path=args.assurance_watch_signoff_verification_report,
            require_final_readiness=args.require_final_readiness,
            final_handoff_package_path=args.final_handoff_package,
            final_handoff_verification_report_path=args.final_handoff_verification_report,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_trust_operations_hub_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_trust_operations_hub_verification_report(report)
        raise SystemExit(trust_operations_hub_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-trust-operations-assurance-watch-package":
        from song_agent.trust_operations_assurance_watch_verifier import (
            print_trust_operations_assurance_watch_verification_report,
            trust_operations_assurance_watch_verification_exit_code,
            verify_trust_operations_assurance_watch_package,
            write_trust_operations_assurance_watch_verification_report,
        )

        parser = build_verify_trust_operations_assurance_watch_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_trust_operations_assurance_watch_package(
            args.zip_path,
            strict=args.strict,
            require_clear=args.require_clear,
            require_current=args.require_current,
            **_trust_operations_assurance_watch_source_payload(args),
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_trust_operations_assurance_watch_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_trust_operations_assurance_watch_verification_report(report)
        raise SystemExit(trust_operations_assurance_watch_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-trust-operations-assurance-watch-signoff-archive-package":
        from song_agent.trust_operations_assurance_watch_signoff_verifier import (
            print_trust_operations_assurance_watch_signoff_verification_report,
            trust_operations_assurance_watch_signoff_verification_exit_code,
            verify_trust_operations_assurance_watch_signoff_archive_package,
            write_trust_operations_assurance_watch_signoff_verification_report,
        )

        parser = build_verify_trust_operations_assurance_watch_signoff_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_trust_operations_assurance_watch_signoff_archive_package(
            args.zip_path,
            strict=args.strict,
            require_signed=args.require_signed,
            require_current=args.require_current,
            watch_package_path=args.watch_package,
            watch_verification_report_path=args.watch_verification_report,
            hub_package_path=args.hub_package,
            hub_verification_report_path=args.hub_verification_report,
            continuous_assurance_report_path=args.continuous_assurance_report,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_trust_operations_assurance_watch_signoff_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_trust_operations_assurance_watch_signoff_verification_report(report)
        raise SystemExit(trust_operations_assurance_watch_signoff_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-trust-operations-final-handoff-package":
        from song_agent.trust_operations_final_readiness_verifier import (
            print_trust_operations_final_handoff_verification_report,
            trust_operations_final_handoff_verification_exit_code,
            verify_trust_operations_final_handoff_package,
            write_trust_operations_final_handoff_verification_report,
        )

        parser = build_verify_trust_operations_final_handoff_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_trust_operations_final_handoff_package(
            args.zip_path,
            strict=args.strict,
            require_signed=args.require_signed,
            require_current=args.require_current,
            **_trust_operations_final_readiness_source_payload(args),
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_trust_operations_final_handoff_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_trust_operations_final_handoff_verification_report(report)
        raise SystemExit(trust_operations_final_handoff_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-trust-operations-assurance-package":
        from song_agent.trust_operations_continuous_assurance_verifier import (
            print_trust_operations_assurance_verification_report,
            trust_operations_assurance_verification_exit_code,
            verify_trust_operations_assurance_package,
            write_trust_operations_assurance_verification_report,
        )

        parser = build_verify_trust_operations_assurance_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_trust_operations_assurance_package(
            args.zip_path,
            strict=args.strict,
            require_passed=args.require_passed,
            require_current=args.require_current,
            **_trust_operations_assurance_source_payload(args),
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_trust_operations_assurance_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_trust_operations_assurance_verification_report(report)
        raise SystemExit(trust_operations_assurance_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-trust-operations-control-package":
        from song_agent.trust_operations_controls_verifier import (
            print_trust_operations_control_verification_report,
            trust_operations_control_verification_exit_code,
            verify_trust_operations_control_package,
            write_trust_operations_control_verification_report,
        )

        parser = build_verify_trust_operations_control_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_trust_operations_control_package(
            args.zip_path,
            strict=args.strict,
            require_policy_passed=args.require_policy_passed,
            hub_package_path=args.hub_package,
            hub_verification_report_path=args.hub_verification_report,
            incident_board_package_path=args.incident_board_package,
            incident_board_verification_report_path=args.incident_board_verification_report,
            incident_knowledge_package_path=args.incident_knowledge_package,
            incident_knowledge_verification_report_path=args.incident_knowledge_verification_report,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_trust_operations_control_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_trust_operations_control_verification_report(report)
        raise SystemExit(trust_operations_control_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-trust-operations-control-signoff-archive-package":
        from song_agent.trust_operations_control_signoff_verifier import (
            print_trust_operations_control_signoff_verification_report,
            trust_operations_control_signoff_verification_exit_code,
            verify_trust_operations_control_signoff_archive_package,
            write_trust_operations_control_signoff_verification_report,
        )

        parser = build_verify_trust_operations_control_signoff_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_trust_operations_control_signoff_archive_package(
            args.zip_path,
            strict=args.strict,
            require_signed=args.require_signed,
            require_current=args.require_current,
            control_package_path=args.control_package,
            control_verification_report_path=args.control_verification_report,
            hub_package_path=args.hub_package,
            hub_verification_report_path=args.hub_verification_report,
            incident_board_package_path=args.incident_board_package,
            incident_board_verification_report_path=args.incident_board_verification_report,
            incident_knowledge_package_path=args.incident_knowledge_package,
            incident_knowledge_verification_report_path=args.incident_knowledge_verification_report,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_trust_operations_control_signoff_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_trust_operations_control_signoff_verification_report(report)
        raise SystemExit(trust_operations_control_signoff_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-trust-operations-incident-knowledge-package":
        from song_agent.trust_operations_incident_knowledge_verifier import (
            print_trust_operations_incident_knowledge_verification_report,
            trust_operations_incident_knowledge_verification_exit_code,
            verify_trust_operations_incident_knowledge_package,
            write_trust_operations_incident_knowledge_verification_report,
        )

        parser = build_verify_trust_operations_incident_knowledge_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_trust_operations_incident_knowledge_package(
            args.zip_path,
            strict=args.strict,
            require_guards_passed=args.require_guards_passed,
            require_no_open_recurrence=args.require_no_open_recurrence,
            incident_board_package_path=args.incident_board_package,
            incident_board_verification_report_path=args.incident_board_verification_report,
            hub_verification_report_path=args.hub_verification_report,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_trust_operations_incident_knowledge_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_trust_operations_incident_knowledge_verification_report(report)
        raise SystemExit(trust_operations_incident_knowledge_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-trust-operations-hub-incident-package":
        from song_agent.trust_operations_hub_incident_verifier import (
            print_trust_operations_hub_incident_verification_report,
            trust_operations_hub_incident_verification_exit_code,
            verify_trust_operations_hub_incident_package,
            write_trust_operations_hub_incident_verification_report,
        )

        parser = build_verify_trust_operations_hub_incident_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_trust_operations_hub_incident_package(
            args.zip_path,
            strict=args.strict,
            require_no_open_critical=args.require_no_open_critical,
            require_no_open_blocking=args.require_no_open_blocking,
            require_current_hub=args.require_current_hub,
            hub_verification_report_path=args.hub_verification_report,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_trust_operations_hub_incident_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_trust_operations_hub_incident_verification_report(report)
        raise SystemExit(trust_operations_hub_incident_verification_exit_code(report))
    elif raw_args and raw_args[0] == "verify-trust-operations-hub-runbook-package":
        from song_agent.trust_operations_hub_runbook_verifier import (
            print_trust_operations_hub_runbook_verification_report,
            trust_operations_hub_runbook_verification_exit_code,
            verify_trust_operations_hub_runbook_package,
            write_trust_operations_hub_runbook_verification_report,
        )

        parser = build_verify_trust_operations_hub_runbook_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_trust_operations_hub_runbook_package(
            args.zip_path,
            strict=args.strict,
            require_completed=args.require_completed,
            require_no_blocked=args.require_no_blocked,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_trust_operations_hub_runbook_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_trust_operations_hub_runbook_verification_report(report)
        raise SystemExit(trust_operations_hub_runbook_verification_exit_code(report))
    elif raw_args and raw_args[0] == "release-operations":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore, operations_report_summary
        from song_agent.release_operations_verifier import release_operations_verification_summary, verify_release_operations_package
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_operations_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        store = ReleaseOperationsStore(
            release_store=release_store,
            distribution_store=distribution_store,
            submission_store=submission_store,
            submission_evidence_store=SubmissionEvidenceStore(submission_store),
        )
        result: dict[str, Any] = {"ok": True, "release_id": args.release_id}
        if args.refresh:
            report = store.refresh(args.release_id)
            result.update({"report": report, "summary": operations_report_summary(report)})
        else:
            overview = store.overview(args.release_id)
            result.update(overview)
        if args.export:
            manifest = store.export_operations(args.release_id)
            result.update({"manifest": manifest, "export_summary": manifest.get("summary", {})})
        if args.zip:
            zip_info = store.build_zip(args.release_id)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_operations_package(store.zip_path(args.release_id), require_accepted=args.require_accepted, require_submission_evidence=args.require_submission_evidence)
            result.update({"verification": verification, "verification_summary": release_operations_verification_summary(verification)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_operations_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-operations-runbook":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore, runbook_summary
        from song_agent.release_operations_runbook_verifier import release_operations_runbook_verification_summary, verify_release_operations_runbook_package
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_operations_runbook_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        result: dict[str, Any] = {"ok": True, "release_id": args.release_id}
        if args.list:
            runbooks = store.list_runbooks(args.release_id, include_archived=True)
            result.update({"runbooks": runbooks, "summary": {"count": len(runbooks)}})
        elif args.create:
            runbook = store.create_from_operations_report(args.release_id)
            result.update({"runbook": runbook, "summary": runbook_summary(runbook)})
        else:
            if not args.runbook_id:
                raise ValueError("--runbook-id is required unless --create or --list is used.")
            runbook = store.get_runbook(args.release_id, args.runbook_id)
            result.update({"runbook": runbook, "summary": runbook_summary(runbook)})
            if args.run_safe:
                runbook = store.run_safe_actions(args.release_id, args.runbook_id)
                result.update({"runbook": runbook, "summary": runbook_summary(runbook)})
            if args.refresh_stale:
                stale_result = store.refresh_stale_status(args.release_id, args.runbook_id)
                result.update(stale_result)
                result["summary"] = runbook_summary(stale_result.get("runbook", {}))
            if args.export:
                manifest = store.export_runbook(args.release_id, args.runbook_id)
                result.update({"manifest": manifest})
            if args.zip:
                zip_info = store.build_zip(args.release_id, args.runbook_id)
                result.update({"zip": zip_info})
            if args.verify:
                verification = verify_release_operations_runbook_package(store.zip_path(args.release_id, args.runbook_id), require_completed=args.require_completed, require_current=args.require_current)
                result.update({"verification": verification, "verification_summary": release_operations_runbook_verification_summary(verification)})
            if args.archive:
                runbook = store.archive_runbook(args.release_id, args.runbook_id)
                result.update({"runbook": runbook, "summary": runbook_summary(runbook)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_operations_runbook_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-operations-signoff":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore, operations_signoff_summary
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_operations_signoff_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        result: dict[str, Any] = {"ok": True, "release_id": args.release_id}
        if args.reset:
            signoff = store.reset_signoff(args.release_id, {"reason": args.reason, "change_request_id": args.change_request_id})
        elif args.sign:
            signoff = store.signoff(args.release_id, {"signed_by": args.signed_by, "force": args.force, "override_reason": args.override_reason})
        else:
            signoff = store.read_signoff(args.release_id, default={})
            result["gate"] = store.gate(args.release_id, {})
        current_report = operations_store.build_report(args.release_id, persist=False) if signoff else None
        result.update({"signoff": signoff, "summary": operations_signoff_summary(signoff, current_report=current_report)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_operations_signoff_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-operations-archive":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_archive_verifier import release_operations_archive_verification_summary, verify_release_operations_archive_package
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_operations_archive_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        result: dict[str, Any] = {"ok": True, "release_id": args.release_id}
        if args.export:
            result["manifest"] = store.export_archive(args.release_id)
        if args.zip:
            result["zip"] = store.build_archive_zip(args.release_id)
        if args.verify:
            verification = verify_release_operations_archive_package(store.archive_zip_path(args.release_id), strict=args.strict, require_signed=args.require_signed)
            result.update({"verification": verification, "verification_summary": release_operations_archive_verification_summary(verification)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_operations_archive_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-operations-audit":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_audit import ReleaseOperationsAuditStore, audit_summary
        from song_agent.release_operations_audit_verifier import release_operations_audit_verification_summary, verify_release_operations_audit_package
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_operations_audit_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
        result: dict[str, Any] = {"ok": True, "release_id": args.release_id}
        if args.refresh:
            report = store.refresh(args.release_id)
            result.update({"report": report, "summary": audit_summary(report)})
        else:
            report = store.read_report(args.release_id, default={})
            result.update({"report": report, "summary": audit_summary(report) if report else {"status": "missing", "entry_count": 0}})
        if args.entries:
            entries = store.entries(args.release_id)
            result.update({"entries": entries, "entry_summary": {"entry_count": len(entries)}})
        if args.graph:
            result["graph"] = store.graph(args.release_id)
        if args.export:
            result["manifest"] = store.export_audit(args.release_id)
        if args.zip:
            result["zip"] = store.build_zip(args.release_id)
        if args.verify:
            verification = verify_release_operations_audit_package(store.zip_path(args.release_id), strict=args.strict, require_current=args.require_current, require_signed=args.require_signed, require_archive=args.require_archive)
            result.update({"verification": verification, "verification_summary": release_operations_audit_verification_summary(verification)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_operations_audit_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-operations-reviewer-pack":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_audit import ReleaseOperationsAuditStore
        from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore, reviewer_pack_summary
        from song_agent.release_operations_reviewer_pack_verifier import release_operations_reviewer_pack_verification_summary, verify_release_operations_reviewer_pack, write_release_operations_reviewer_pack_verification_report
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
        from song_agent.release_operations_retrospective import retrospective_summary
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_operations_reviewer_pack_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
        store = ReleaseOperationsReviewerPackStore(audit_store=audit_store, signoff_store=signoff_store, release_store=release_store)
        result: dict[str, Any] = {"ok": True, "release_id": args.release_id}
        if args.refresh:
            report = store.refresh(args.release_id)
            result.update({"report": report, "summary": reviewer_pack_summary(report), "retrospective_summary": retrospective_summary(store.read_retrospective(args.release_id, default={}))})
        else:
            report = store.read_report(args.release_id, default={})
            result.update({"report": report, "summary": reviewer_pack_summary(report), "retrospective_summary": retrospective_summary(store.read_retrospective(args.release_id, default={})) if report else {"status": "missing"}})
        if args.export:
            manifest = store.export_pack(args.release_id)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_zip(args.release_id)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_operations_reviewer_pack(store.zip_path(args.release_id), strict=args.strict, require_audit=args.require_audit, require_signed=args.require_signed, require_archive=args.require_archive)
            write_release_operations_reviewer_pack_verification_report(verification, store.verification_report_path(args.release_id))
            result.update({"verification": verification, "verification_summary": release_operations_reviewer_pack_verification_summary(verification)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_operations_reviewer_pack_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-audit":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_audit import ReleaseOperationsAuditStore
        from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
        from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore, portfolio_audit_summary
        from song_agent.release_portfolio_audit_verifier import release_portfolio_audit_verification_summary, verify_release_portfolio_audit_package, write_release_portfolio_audit_verification_report
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_portfolio_audit_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
        reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=audit_store, signoff_store=signoff_store, release_store=release_store)
        store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, audit_store=audit_store, reviewer_pack_store=reviewer_store)
        result: dict[str, Any] = {"ok": True}
        release_ids = [item.strip() for item in str(args.release_ids or "").split(",") if item.strip()]
        payload = {
            "name": args.name,
            "release_ids": release_ids,
            "include_hidden": args.include_hidden,
            "include_archived": not args.exclude_archived,
            "max_releases": args.max_releases,
            "require_reviewer_packs": args.require_reviewer_packs,
            "require_audit": args.require_audit,
            "require_archive": args.require_archive,
        }
        if args.list:
            portfolios = store.list_portfolios(include_archived=True)
            result.update({"portfolios": portfolios, "summary": {"count": len(portfolios)}})
        else:
            if args.create:
                portfolio = store.create(payload)
                result.update({"portfolio": portfolio, "portfolio_id": portfolio.get("portfolio_id")})
            else:
                if not args.portfolio_id:
                    raise ValueError("--portfolio-id is required unless --create or --list is used.")
                portfolio = store.get_portfolio(args.portfolio_id)
                result.update({"portfolio": portfolio, "portfolio_id": args.portfolio_id})
            portfolio_id = str(result.get("portfolio_id") or args.portfolio_id)
            if args.refresh:
                report = store.refresh(portfolio_id, payload)
                summary = portfolio_audit_summary(report)
                summary["stale"] = store.report_is_stale(portfolio_id, report)
                result.update({"report": report, "summary": summary, "stale": summary["stale"], "trend_report": store.read_trend_report(portfolio_id, default={}), "risk_register": store.read_risk_register(portfolio_id, default={})})
            elif not args.create:
                report = store.read_report(portfolio_id, default={})
                summary = portfolio_audit_summary(report) if report else {"status": "missing"}
                if report:
                    summary["stale"] = store.report_is_stale(portfolio_id, report)
                result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
            if args.export:
                manifest = store.export_portfolio(portfolio_id)
                result.update({"manifest": manifest})
            if args.zip:
                zip_info = store.build_zip(portfolio_id)
                result.update({"zip": zip_info})
            if args.verify:
                verification = verify_release_portfolio_audit_package(store.zip_path(portfolio_id), strict=args.strict, require_reviewer_packs=args.require_reviewer_packs, require_audit=args.require_audit, require_archive=args.require_archive)
                write_release_portfolio_audit_verification_report(verification, store.verification_report_path(portfolio_id))
                result.update({"verification": verification, "verification_summary": release_portfolio_audit_verification_summary(verification)})
            if args.archive:
                portfolio = store.archive(portfolio_id)
                result.update({"portfolio": portfolio})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_audit_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-governance-queue":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_audit import ReleaseOperationsAuditStore
        from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
        from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
        from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore, queue_summary
        from song_agent.release_portfolio_governance_verifier import release_portfolio_governance_verification_summary, verify_release_portfolio_governance_package, write_release_portfolio_governance_verification_report
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_portfolio_governance_queue_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
        reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=audit_store, signoff_store=signoff_store, release_store=release_store)
        portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, audit_store=audit_store, reviewer_pack_store=reviewer_store)
        store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=reviewer_store, audit_store=audit_store, signoff_store=signoff_store)
        result: dict[str, Any] = {"ok": True}
        if args.list:
            queues = store.list_queues(portfolio_id=args.portfolio_id or None, include_archived=True)
            result.update({"queues": queues, "summary": {"count": len(queues)}})
        else:
            if args.create:
                if not args.portfolio_id:
                    raise ValueError("--portfolio-id is required with --create.")
                queue = store.create_from_portfolio(args.portfolio_id, {"name": args.name, "force_new": args.force_new})
                result.update({"queue": queue, "queue_id": queue.get("queue_id"), "summary": queue_summary(queue)})
            else:
                if not args.queue_id:
                    raise ValueError("--queue-id is required unless --create or --list is used.")
                queue = store.get_queue(args.queue_id)
                execution = store.read_execution_report(args.queue_id, default={})
                result.update({"queue": queue, "queue_id": args.queue_id, "summary": queue_summary(queue, execution), "execution_report": execution})
            queue_id = str(result.get("queue_id") or args.queue_id)
            if args.run_safe:
                queue = store.run_safe_actions(queue_id, {"refresh_portfolio_after_safe_actions": args.refresh_portfolio_after_safe_actions})
                execution = store.read_execution_report(queue_id, default={})
                result.update({"queue": queue, "execution_report": execution, "summary": queue_summary(queue, execution)})
            if args.export:
                manifest = store.export_queue(queue_id)
                result.update({"manifest": manifest})
            if args.zip:
                zip_info = store.build_zip(queue_id)
                result.update({"zip": zip_info})
            if args.verify:
                verification = verify_release_portfolio_governance_package(store.zip_path(queue_id), strict=args.strict, require_manual_actions=args.require_manual_actions, require_no_blocked=args.require_no_blocked)
                write_release_portfolio_governance_verification_report(verification, store.verification_report_path(queue_id))
                result.update({"verification": verification, "verification_summary": release_portfolio_governance_verification_summary(verification)})
            if args.archive:
                queue = store.archive(queue_id)
                result.update({"queue": queue, "summary": queue_summary(queue)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-governance-signoff":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_audit import ReleaseOperationsAuditStore
        from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
        from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
        from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
        from song_agent.release_portfolio_governance_archive_verifier import release_portfolio_governance_archive_verification_summary, verify_release_portfolio_governance_archive_package, write_release_portfolio_governance_archive_verification_report
        from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_portfolio_governance_signoff_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
        reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=audit_store, signoff_store=operations_signoff_store, release_store=release_store)
        portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=audit_store, reviewer_pack_store=reviewer_store)
        governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=reviewer_store, audit_store=audit_store, signoff_store=operations_signoff_store)
        store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
        queue_id = args.queue_id
        result: dict[str, Any] = {"ok": True, "queue_id": queue_id}
        if args.create_change_request:
            change = store.create_change_request(queue_id, {"reason": args.reason, "requested_by": args.signed_by})
            result.update({"change_request": change, "change_request_summary": store.change_request_summary(queue_id)})
        if args.approve_change_request:
            change = store.update_change_request_status(queue_id, args.approve_change_request, "approve", {"approved_by": args.approved_by})
            result.update({"change_request": change, "change_request_summary": store.change_request_summary(queue_id)})
        if args.reject_change_request:
            change = store.update_change_request_status(queue_id, args.reject_change_request, "reject", {"reason": args.reason or "Rejected by local reviewer"})
            result.update({"change_request": change, "change_request_summary": store.change_request_summary(queue_id)})
        if args.reset:
            signoff = store.reset_signoff(queue_id, {"reason": args.reason, "change_request_id": args.change_request_id, "reset_by": args.signed_by})
            result.update({"signoff": signoff, "summary": store.signoff_summary(queue_id, signoff=signoff)})
        if args.sign:
            manual = governance_store.read_manual_action_list(queue_id, default={})
            acknowledgements = [
                {"item_id": item.get("item_id"), "action_type": item.get("action_type"), "resolution": "accepted_for_followup", "owner": args.signed_by, "due_note": "tracked outside CLI signoff"}
                for item in manual.get("items", [])
                if isinstance(item, dict)
            ]
            signoff = store.signoff(queue_id, {"signed_by": args.signed_by, "force": args.force, "override_reason": args.override_reason, "manual_acknowledgements": acknowledgements})
            result.update({"signoff": signoff, "summary": store.signoff_summary(queue_id, signoff=signoff)})
        if args.export_archive:
            manifest = store.export_archive(queue_id)
            result.update({"manifest": manifest, "archive_summary": store.archive_summary(queue_id)})
        if args.zip:
            zip_info = store.build_archive_zip(queue_id)
            result.update({"zip": zip_info, "archive_summary": store.archive_summary(queue_id)})
        if args.verify:
            verification = verify_release_portfolio_governance_archive_package(store.archive_zip_path(queue_id), strict=args.strict, require_signed=args.require_signed, require_no_force=args.require_no_force)
            write_release_portfolio_governance_archive_verification_report(verification, store.archive_verification_report_path(queue_id))
            result.update({"verification": verification, "verification_summary": release_portfolio_governance_archive_verification_summary(verification)})
        if "summary" not in result:
            signoff = store.read_signoff(queue_id, default={})
            result.update({"signoff": signoff, "summary": store.signoff_summary(queue_id, signoff=signoff), "archive_summary": store.archive_summary(queue_id), "change_request_summary": store.change_request_summary(queue_id)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_signoff_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-governance-audit":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_audit import ReleaseOperationsAuditStore
        from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
        from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
        from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
        from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore, audit_summary as portfolio_governance_audit_summary
        from song_agent.release_portfolio_governance_audit_verifier import release_portfolio_governance_audit_verification_summary, verify_release_portfolio_governance_audit_package, write_release_portfolio_governance_audit_verification_report
        from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_portfolio_governance_audit_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
        reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
        portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=reviewer_store)
        governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
        signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
        store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=signoff_store)
        portfolio_id = args.portfolio_id
        result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id}
        if args.refresh:
            report = store.refresh(portfolio_id)
            result.update({"report": report, "summary": portfolio_governance_audit_summary(report), "stale": store.report_is_stale(portfolio_id, report)})
        else:
            report = store.read_report(portfolio_id, default={})
            summary = portfolio_governance_audit_summary(report) if report else {"status": "missing"}
            if report:
                summary["stale"] = store.report_is_stale(portfolio_id, report)
            result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
        if args.ledger:
            entries = store.read_ledger(portfolio_id)
            if args.ledger_limit and args.ledger_limit > 0:
                entries = entries[-args.ledger_limit :]
            result.update({"ledger": entries, "ledger_summary": {"entry_count": len(entries)}})
        if args.export:
            manifest = store.export_audit(portfolio_id)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_zip(portfolio_id)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_portfolio_governance_audit_package(
                store.zip_path(portfolio_id),
                strict=args.strict,
                require_signed=args.require_signed,
                require_archives=args.require_archives,
                require_no_force=args.require_no_force,
                require_reset_cr_causality=args.require_reset_cr_causality,
            )
            write_release_portfolio_governance_audit_verification_report(verification, store.verification_report_path(portfolio_id))
            result.update({"verification": verification, "verification_summary": release_portfolio_governance_audit_verification_summary(verification)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_audit_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-governance-reviewer-pack":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_audit import ReleaseOperationsAuditStore
        from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
        from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
        from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
        from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
        from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore, reviewer_pack_summary as portfolio_governance_reviewer_pack_summary
        from song_agent.release_portfolio_governance_reviewer_pack_verifier import release_portfolio_governance_reviewer_pack_verification_summary, verify_release_portfolio_governance_reviewer_pack, write_release_portfolio_governance_reviewer_pack_verification_report
        from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_portfolio_governance_reviewer_pack_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
        operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
        portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
        governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
        signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
        audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=signoff_store)
        store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=audit_store)
        portfolio_id = args.portfolio_id
        result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id}
        if args.refresh:
            report = store.refresh(portfolio_id)
            result.update({"report": report, "summary": portfolio_governance_reviewer_pack_summary(report), "stale": store.report_is_stale(portfolio_id, report)})
        else:
            report = store.read_report(portfolio_id, default={})
            summary = portfolio_governance_reviewer_pack_summary(report) if report else {"status": "missing"}
            if report:
                summary["stale"] = store.report_is_stale(portfolio_id, report)
            result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
        result.update({"retrospective": store.read_retrospective(portfolio_id, default={}), "evidence_index": store.read_evidence_index(portfolio_id, default={}), "timeline": store.read_timeline(portfolio_id, default={})})
        if args.export:
            manifest = store.export_pack(portfolio_id)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_zip(portfolio_id)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_portfolio_governance_reviewer_pack(
                store.zip_path(portfolio_id),
                strict=args.strict,
                require_audit=args.require_audit,
                require_signed=args.require_signed,
                require_archives=args.require_archives,
                require_no_force=args.require_no_force,
                require_reset_cr_causality=args.require_reset_cr_causality,
            )
            write_release_portfolio_governance_reviewer_pack_verification_report(verification, store.verification_report_path(portfolio_id))
            result.update({"verification": verification, "verification_summary": release_portfolio_governance_reviewer_pack_verification_summary(verification)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_reviewer_pack_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-governance-final-board":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_audit import ReleaseOperationsAuditStore
        from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
        from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
        from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
        from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
        from song_agent.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore, final_board_summary as portfolio_governance_final_board_summary
        from song_agent.release_portfolio_governance_final_board_verifier import release_portfolio_governance_final_board_verification_summary, verify_release_portfolio_governance_final_board_package, write_release_portfolio_governance_final_board_verification_report
        from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore
        from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_portfolio_governance_final_board_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
        operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
        portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
        governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
        governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
        governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
        governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
        store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
        portfolio_id = args.portfolio_id
        result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id}
        if args.import_reviewer_response is not None:
            response_payload = read_json(args.import_reviewer_response)
            response = store.import_reviewer_response(portfolio_id, response_payload)
            result.update({"reviewer_response": response})
        refresh_payload = {"require_reviewer_response": args.require_reviewer_response, "require_no_force": args.require_no_force}
        if args.refresh or args.import_reviewer_response is not None:
            report = store.refresh_report(portfolio_id, refresh_payload)
            result.update({"report": report, "summary": portfolio_governance_final_board_summary(report), "stale": store.report_is_stale(portfolio_id, report)})
        else:
            report = store.read_report(portfolio_id, default={})
            summary = portfolio_governance_final_board_summary(report) if report else {"status": "missing"}
            if report:
                summary["stale"] = store.report_is_stale(portfolio_id, report)
            result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
        if args.create_change_request:
            change = store.create_change_request(portfolio_id, {"reason": args.reason or "Final Board archive change requested."})
            result.update({"change_request": change})
        if args.approve_change_request:
            change = store.update_change_request_status(portfolio_id, args.approve_change_request, "approve", {"approved_by": args.approved_by or args.signed_by or "local-user"})
            result.update({"change_request": change})
        if args.reject_change_request:
            change = store.update_change_request_status(portfolio_id, args.reject_change_request, "reject", {"reason": args.reason or "Final Board change rejected."})
            result.update({"change_request": change})
        if args.reset_signoff:
            reset = store.reset_signoff(portfolio_id, {"reason": args.reason or "Final Board signoff reset requested.", "change_request_id": args.change_request_id, "reset_by": args.signed_by or "local-user"})
            result.update({"signoff": reset, "signoff_summary": store.signoff_summary(portfolio_id, signoff=reset)})
        if args.sign or args.force_sign:
            signoff = store.signoff(
                portfolio_id,
                {
                    "signed_by": args.signed_by or "local-user",
                    "role": args.role,
                    "reason": args.reason,
                    "force": bool(args.force_sign),
                    "allow_warning_signoff": bool(args.allow_warning_signoff),
                    "override_reason": args.override_reason,
                },
            )
            result.update({"signoff": signoff, "signoff_summary": store.signoff_summary(portfolio_id, signoff=signoff)})
        if args.export:
            manifest = store.export_archive(portfolio_id)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_archive_zip(portfolio_id)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_portfolio_governance_final_board_package(
                store.archive_zip_path(portfolio_id),
                strict=args.strict,
                require_signed=args.require_signed,
                require_reviewer_pack=args.require_reviewer_pack,
                require_audit=args.require_audit,
                require_archives=args.require_archives,
                require_reviewer_response=args.require_reviewer_response,
                require_no_force=args.require_no_force,
                require_reset_cr_causality=args.require_reset_cr_causality,
            )
            write_release_portfolio_governance_final_board_verification_report(verification, store.verification_report_path(portfolio_id))
            result.update({"verification": verification, "verification_summary": release_portfolio_governance_final_board_verification_summary(verification)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_final_board_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-governance-evidence-vault":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_audit import ReleaseOperationsAuditStore
        from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
        from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
        from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
        from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
        from song_agent.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore, evidence_vault_summary as portfolio_governance_evidence_vault_summary, evidence_vault_verification_summary as release_portfolio_governance_evidence_vault_verification_summary
        from song_agent.release_portfolio_governance_evidence_vault_verifier import verify_release_portfolio_governance_evidence_vault_package, write_release_portfolio_governance_evidence_vault_verification_report
        from song_agent.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore
        from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore
        from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_portfolio_governance_evidence_vault_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
        operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
        portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
        governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
        governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
        governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
        governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
        final_board_store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
        store = ReleasePortfolioGovernanceEvidenceVaultStore(
            portfolio_store=portfolio_store,
            governance_store=governance_store,
            signoff_store=governance_signoff_store,
            audit_store=governance_audit_store,
            reviewer_pack_store=governance_reviewer_store,
            final_board_store=final_board_store,
        )
        portfolio_id = args.portfolio_id
        result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id}
        refresh_payload = {
            "require_final_board": True,
            "require_reviewer_pack": True,
            "require_audit": True,
            "require_archives": True,
            "require_queue_packages": args.require_queue_packages,
        }
        if args.refresh:
            report = store.refresh_report(portfolio_id, refresh_payload)
            result.update({"report": report, "summary": portfolio_governance_evidence_vault_summary(report), "stale": store.report_is_stale(portfolio_id, report)})
        else:
            report = store.read_report(portfolio_id, default={})
            summary = portfolio_governance_evidence_vault_summary(report) if report else {"status": "missing"}
            if report:
                summary["stale"] = store.report_is_stale(portfolio_id, report)
            result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
        result.update({"package_index": store.read_package_index(portfolio_id, default={}), "verification_index": store.read_verification_index(portfolio_id, default={}), "chain_of_custody": store.read_chain_of_custody(portfolio_id, default={})})
        if args.export:
            manifest = store.export_vault(portfolio_id)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_zip(portfolio_id)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_portfolio_governance_evidence_vault_package(
                store.zip_path(portfolio_id),
                strict=args.strict,
                deep=args.deep,
                require_final_board=args.require_final_board,
                require_reviewer_pack=args.require_reviewer_pack,
                require_audit=args.require_audit,
                require_archives=args.require_archives,
                require_queue_packages=args.require_queue_packages,
            )
            write_release_portfolio_governance_evidence_vault_verification_report(verification, store.verification_report_path(portfolio_id))
            result.update({"verification": verification, "verification_summary": release_portfolio_governance_evidence_vault_verification_summary(verification)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_evidence_vault_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-governance-attestation":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_audit import ReleaseOperationsAuditStore
        from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
        from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
        from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
        from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
        from song_agent.release_portfolio_governance_attestation import ReleasePortfolioGovernanceAttestationStore, attestation_summary as portfolio_governance_attestation_summary, attestation_verification_summary as release_portfolio_governance_attestation_verification_summary
        from song_agent.release_portfolio_governance_attestation_verifier import verify_release_portfolio_governance_attestation, write_release_portfolio_governance_attestation_verification_report
        from song_agent.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore
        from song_agent.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore
        from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore
        from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_portfolio_governance_attestation_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
        operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
        portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
        governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
        governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
        governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
        governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
        final_board_store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
        vault_store = ReleasePortfolioGovernanceEvidenceVaultStore(
            portfolio_store=portfolio_store,
            governance_store=governance_store,
            signoff_store=governance_signoff_store,
            audit_store=governance_audit_store,
            reviewer_pack_store=governance_reviewer_store,
            final_board_store=final_board_store,
        )
        store = ReleasePortfolioGovernanceAttestationStore(portfolio_store=portfolio_store, final_board_store=final_board_store, evidence_vault_store=vault_store)
        portfolio_id = args.portfolio_id
        payload = {"profile": args.profile, "require_no_force": args.require_no_force}
        result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
        if args.refresh:
            report = store.refresh_report(portfolio_id, payload)
            result.update({"report": report, "summary": portfolio_governance_attestation_summary(report), "stale": store.report_is_stale(portfolio_id, report, profile=args.profile)})
        else:
            report = store.read_report(portfolio_id, profile=args.profile, default={})
            summary = portfolio_governance_attestation_summary(report) if report else {"status": "missing", "profile": args.profile}
            if report:
                summary["stale"] = store.report_is_stale(portfolio_id, report, profile=args.profile)
            result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
        certificate = store.read_certificate(portfolio_id, profile=args.profile, default={})
        if certificate:
            result["certificate"] = certificate
        if args.export:
            manifest = store.export_attestation(portfolio_id, payload)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_zip(portfolio_id, payload)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_portfolio_governance_attestation(store.zip_path(portfolio_id, args.profile), strict=args.strict, require_vault=args.require_vault, require_final_board=args.require_final_board)
            write_release_portfolio_governance_attestation_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
            result.update({"verification": verification, "verification_summary": release_portfolio_governance_attestation_verification_summary(verification)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-governance-attestation-registry":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_audit import ReleaseOperationsAuditStore
        from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
        from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
        from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
        from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
        from song_agent.release_portfolio_governance_attestation import ReleasePortfolioGovernanceAttestationStore
        from song_agent.release_portfolio_governance_attestation_registry import ReleasePortfolioGovernanceAttestationRegistryStore, registry_summary as portfolio_governance_attestation_registry_summary, registry_verification_summary as release_portfolio_governance_attestation_registry_verification_summary
        from song_agent.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry, write_release_portfolio_governance_attestation_registry_verification_report
        from song_agent.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore
        from song_agent.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore
        from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore
        from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_portfolio_governance_attestation_registry_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
        operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
        portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
        governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
        governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
        governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
        governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
        final_board_store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
        vault_store = ReleasePortfolioGovernanceEvidenceVaultStore(
            portfolio_store=portfolio_store,
            governance_store=governance_store,
            signoff_store=governance_signoff_store,
            audit_store=governance_audit_store,
            reviewer_pack_store=governance_reviewer_store,
            final_board_store=final_board_store,
        )
        attestation_store = ReleasePortfolioGovernanceAttestationStore(portfolio_store=portfolio_store, final_board_store=final_board_store, evidence_vault_store=vault_store)
        store = ReleasePortfolioGovernanceAttestationRegistryStore(attestation_store=attestation_store)
        portfolio_id = args.portfolio_id
        payload = {"profile": args.profile}
        result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
        if args.register_current:
            registered = store.register_current_attestation(portfolio_id, {**payload, "public_url": args.public_url, "distribution_note": args.distribution_note})
            result.update({"entry": registered.get("entry"), "registry": registered.get("registry"), "existing": bool(registered.get("existing"))})
        if args.publish:
            published = store.publish_entry(portfolio_id, args.publish, {**payload, "supersede_current": args.supersede_current, "public_url": args.public_url, "distribution_note": args.distribution_note, "published_by": "cli"})
            result.update({"entry": published.get("entry"), "registry": published.get("registry")})
        if args.revoke:
            revoked = store.revoke_entry(portfolio_id, args.revoke, {**payload, "reason": args.reason, "revoked_by": "cli"})
            result.update({"entry": revoked.get("entry"), "registry": revoked.get("registry")})
        if args.refresh:
            report = store.refresh_report(portfolio_id, payload)
            result.update({"report": report})
        else:
            report = store.read_report(portfolio_id, profile=args.profile, default={})
            if report:
                result["report"] = report
        registry = result.get("registry") if isinstance(result.get("registry"), dict) else store.read_registry(portfolio_id, profile=args.profile, default={})
        result["registry"] = registry
        result["summary"] = portfolio_governance_attestation_registry_summary(registry) if registry else {"status": "missing", "profile": args.profile}
        if args.export:
            manifest = store.export_registry(portfolio_id, payload)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_zip(portfolio_id, payload)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_portfolio_governance_attestation_registry(store.zip_path(portfolio_id, args.profile), strict=args.strict, require_current=args.require_current, require_published=args.require_published, require_no_revoked_current=args.require_no_revoked_current, require_accepted_evidence=args.require_accepted_evidence)
            write_release_portfolio_governance_attestation_registry_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
            result.update({"verification": verification, "verification_summary": release_portfolio_governance_attestation_registry_verification_summary(verification)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_registry_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-governance-attestation-portal":
        from song_agent.distribution import DistributionStore
        from song_agent.release_operations import ReleaseOperationsStore
        from song_agent.release_operations_audit import ReleaseOperationsAuditStore
        from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
        from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
        from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
        from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
        from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
        from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
        from song_agent.release_portfolio_governance_attestation import ReleasePortfolioGovernanceAttestationStore
        from song_agent.release_portfolio_governance_attestation_portal import ReleasePortfolioGovernanceAttestationPortalStore, portal_summary as release_portfolio_governance_attestation_portal_summary, portal_verification_summary as release_portfolio_governance_attestation_portal_verification_summary
        from song_agent.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal, write_release_portfolio_governance_attestation_portal_verification_report
        from song_agent.release_portfolio_governance_attestation_registry import ReleasePortfolioGovernanceAttestationRegistryStore
        from song_agent.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore
        from song_agent.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore
        from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore
        from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
        from song_agent.releases import ReleaseStore
        from song_agent.submission_evidence import SubmissionEvidenceStore
        from song_agent.submissions import SubmissionStore

        parser = build_release_portfolio_governance_attestation_portal_parser()
        args = parser.parse_args(raw_args[1:])
        release_store = ReleaseStore()
        distribution_store = DistributionStore(release_store)
        submission_store = SubmissionStore(release_store, distribution_store)
        evidence_store = SubmissionEvidenceStore(submission_store)
        operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
        operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
        operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
        operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
        portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
        governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
        governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
        governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
        governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
        final_board_store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
        vault_store = ReleasePortfolioGovernanceEvidenceVaultStore(
            portfolio_store=portfolio_store,
            governance_store=governance_store,
            signoff_store=governance_signoff_store,
            audit_store=governance_audit_store,
            reviewer_pack_store=governance_reviewer_store,
            final_board_store=final_board_store,
        )
        attestation_store = ReleasePortfolioGovernanceAttestationStore(portfolio_store=portfolio_store, final_board_store=final_board_store, evidence_vault_store=vault_store)
        registry_store = ReleasePortfolioGovernanceAttestationRegistryStore(attestation_store=attestation_store)
        store = ReleasePortfolioGovernanceAttestationPortalStore(registry_store=registry_store, attestation_store=attestation_store)
        portfolio_id = args.portfolio_id
        payload = {"profile": args.profile}
        result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
        if args.refresh:
            report = store.refresh_report(portfolio_id, payload)
            result.update({"report": report, "summary": release_portfolio_governance_attestation_portal_summary(report), "stale": False})
        else:
            report = store.read_report(portfolio_id, profile=args.profile, default={})
            summary = release_portfolio_governance_attestation_portal_summary(report) if report else {"status": "missing", "profile": args.profile}
            if report:
                summary["stale"] = store.report_is_stale(portfolio_id, report, profile=args.profile)
            result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
        if args.export:
            manifest = store.export_portal(portfolio_id, payload)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_zip(portfolio_id, payload)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_portfolio_governance_attestation_portal(store.zip_path(portfolio_id, args.profile), strict=args.strict, require_current=args.require_current, require_registry=args.require_registry, require_attestation=args.require_attestation, require_accepted_evidence=args.require_accepted_evidence)
            write_release_portfolio_governance_attestation_portal_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
            result.update({"verification": verification, "verification_summary": release_portfolio_governance_attestation_portal_verification_summary(verification)})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_portal_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-governance-attestation-portal-review":
        from song_agent.release_portfolio_governance_attestation_portal_review import (
            ReleasePortfolioGovernanceAttestationPortalReviewStore,
            response_summary as release_portfolio_governance_attestation_portal_response_summary,
            review_pack_summary as release_portfolio_governance_attestation_portal_review_pack_summary,
        )
        from song_agent.release_portfolio_governance_attestation_portal_review_verifier import (
            verify_release_portfolio_governance_attestation_portal_review_pack,
            write_release_portfolio_governance_attestation_portal_review_pack_verification_report,
        )

        parser = build_release_portfolio_governance_attestation_portal_review_parser()
        args = parser.parse_args(raw_args[1:])
        portal_store = _build_release_portfolio_governance_attestation_portal_store()
        store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
        portfolio_id = args.portfolio_id
        result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
        if args.refresh_pack:
            pack = store.refresh_pack(portfolio_id, {"profile": args.profile})
            result.update({"review_pack": pack, "summary": release_portfolio_governance_attestation_portal_review_pack_summary(pack), "stale": False})
        else:
            pack = store.read_pack(portfolio_id, profile=args.profile, default={})
            summary = release_portfolio_governance_attestation_portal_review_pack_summary(pack) if pack else {"status": "missing", "profile": args.profile}
            if pack:
                summary["stale"] = store.pack_is_stale(portfolio_id, pack, profile=args.profile)
            result.update({"review_pack": pack, "summary": summary, "stale": summary.get("stale", False)})
        if args.export_pack:
            manifest = store.export_pack(portfolio_id, {"profile": args.profile})
            result.update({"manifest": manifest})
        if args.zip_pack:
            zip_info = store.build_pack_zip(portfolio_id, {"profile": args.profile})
            result.update({"zip": zip_info})
        if args.verify_pack:
            verification = verify_release_portfolio_governance_attestation_portal_review_pack(
                store.pack_zip_path(portfolio_id, args.profile),
                strict=args.strict,
                require_current=args.require_current,
            )
            write_release_portfolio_governance_attestation_portal_review_pack_verification_report(verification, store.pack_verification_report_path(portfolio_id, args.profile))
            result.update({"verification": verification})
        if args.import_response:
            imported = store.import_response(portfolio_id, {"profile": args.profile, "content_base64": args.content_base64})
            result.update(imported)
        if args.responses:
            result.update({"responses": store.list_responses(portfolio_id, profile=args.profile)})
        if args.response_id and not args.verify_response and not args.create_change_request:
            response = store.get_response(portfolio_id, args.response_id, profile=args.profile)
            result.update({"response": response, "response_summary": release_portfolio_governance_attestation_portal_response_summary(response)})
        if args.verify_response:
            if not args.response_id:
                parser.error("--verify-response requires --response-id")
            verification = store.verify_response(portfolio_id, args.response_id, profile=args.profile)
            result.update({"response_verification": verification})
        if args.create_change_request:
            if not args.response_id:
                parser.error("--create-change-request requires --response-id")
            change = store.create_change_request(portfolio_id, args.response_id, {"created_by": "cli"}, profile=args.profile)
            result.update(change)
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_portal_review_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-governance-attestation-accepted-evidence":
        from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore, accepted_evidence_summary
        from song_agent.release_portfolio_governance_attestation_accepted_evidence_verifier import write_release_portfolio_governance_attestation_accepted_evidence_verification_report
        from song_agent.release_portfolio_governance_attestation_portal_review import ReleasePortfolioGovernanceAttestationPortalReviewStore

        parser = build_release_portfolio_governance_attestation_accepted_evidence_parser()
        args = parser.parse_args(raw_args[1:])
        portal_store = _build_release_portfolio_governance_attestation_portal_store()
        review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
        store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
        portfolio_id = args.portfolio_id
        result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
        if args.refresh:
            payload = {"profile": args.profile}
            if args.response_id:
                payload["response_id"] = args.response_id
            evidence = store.refresh_evidence(portfolio_id, payload)
            result.update({"accepted_evidence": evidence, "summary": accepted_evidence_summary(evidence), "stale": False})
        else:
            evidence = store.read_evidence(portfolio_id, profile=args.profile, default={})
            summary = accepted_evidence_summary(evidence) if evidence else {"status": "missing", "external_review_status": "missing", "profile": args.profile}
            if evidence:
                summary["stale"] = store.evidence_is_stale(portfolio_id, evidence, profile=args.profile)
            result.update({"accepted_evidence": evidence, "summary": summary, "stale": summary.get("stale", False)})
        if args.export:
            result["manifest"] = store.export_evidence(portfolio_id, {"profile": args.profile})
        if args.zip:
            result["zip"] = store.build_zip(portfolio_id, {"profile": args.profile})
        if args.verify:
            verification = store.verify_evidence(portfolio_id, {"profile": args.profile, "strict": args.strict, "require_current": args.require_current})
            write_release_portfolio_governance_attestation_accepted_evidence_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
            result["verification"] = verification
        if args.archive:
            result["accepted_evidence"] = store.archive_evidence(portfolio_id, {"profile": args.profile, "reason": args.reason})
            result["summary"] = accepted_evidence_summary(result["accepted_evidence"])
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_accepted_evidence_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-governance-attestation-transparency":
        from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore
        from song_agent.release_portfolio_governance_attestation_portal_review import ReleasePortfolioGovernanceAttestationPortalReviewStore
        from song_agent.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore, transparency_summary
        from song_agent.release_portfolio_governance_attestation_transparency_verifier import write_release_portfolio_governance_attestation_transparency_verification_report

        parser = build_release_portfolio_governance_attestation_transparency_parser()
        args = parser.parse_args(raw_args[1:])
        portal_store = _build_release_portfolio_governance_attestation_portal_store()
        review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
        accepted_store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
        store = ReleasePortfolioGovernanceAttestationTransparencyStore(
            attestation_store=portal_store.attestation_store,
            registry_store=portal_store.registry_store,
            portal_store=portal_store,
            accepted_evidence_store=accepted_store,
        )
        portfolio_id = args.portfolio_id
        result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
        if args.refresh:
            feed = store.refresh_feed(portfolio_id, {"profile": args.profile, "require_accepted_evidence": args.require_accepted_evidence})
            result.update({"feed": feed, "summary": transparency_summary(feed), "stale": False})
        else:
            feed = store.read_feed(portfolio_id, profile=args.profile, default={})
            summary = transparency_summary(feed) if feed else {"status": "missing", "profile": args.profile}
            if feed:
                summary["stale"] = store.feed_is_stale(portfolio_id, feed, profile=args.profile)
            result.update({"feed": feed, "summary": summary, "stale": summary.get("stale", False)})
        if args.export:
            result["manifest"] = store.export_transparency(portfolio_id, {"profile": args.profile})
        if args.zip:
            result["zip"] = store.build_zip(portfolio_id, {"profile": args.profile})
        if args.verify:
            verification = store.verify_transparency(
                portfolio_id,
                {
                    "profile": args.profile,
                    "strict": args.strict,
                    "require_current": args.require_current,
                    "require_accepted_evidence": args.require_accepted_evidence,
                    "require_no_revoked_current": args.require_no_revoked_current,
                    "require_contiguous_chain": args.require_contiguous_chain,
                },
            )
            write_release_portfolio_governance_attestation_transparency_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
            result["verification"] = verification
        if args.notices:
            result["notices"] = store.list_notices(portfolio_id, profile=args.profile)
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_transparency_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-portfolio-governance-attestation-transparency-acknowledgement":
        from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore
        from song_agent.release_portfolio_governance_attestation_portal_review import ReleasePortfolioGovernanceAttestationPortalReviewStore
        from song_agent.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore
        from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore, acknowledgement_summary
        from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement_verifier import (
            verify_release_portfolio_governance_attestation_transparency_acknowledgement_package,
            write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report,
        )

        parser = build_release_portfolio_governance_attestation_transparency_acknowledgement_parser()
        args = parser.parse_args(raw_args[1:])
        portal_store = _build_release_portfolio_governance_attestation_portal_store()
        review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
        accepted_store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
        transparency_store = ReleasePortfolioGovernanceAttestationTransparencyStore(
            attestation_store=portal_store.attestation_store,
            registry_store=portal_store.registry_store,
            portal_store=portal_store,
            accepted_evidence_store=accepted_store,
        )
        store = ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore(transparency_store=transparency_store)
        portfolio_id = args.portfolio_id
        result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
        if args.refresh_pack:
            pack = store.refresh_pack(portfolio_id, {"profile": args.profile})
            result.update({"pack": pack, "summary": {"status": pack.get("status"), "pack_id": pack.get("pack_id"), "source_hash": pack.get("source_hash")}})
        else:
            pack = store.read_pack(portfolio_id, profile=args.profile, default={})
            result.update({"pack": pack, "summary": {"status": pack.get("status", "missing") if pack else "missing", "pack_id": pack.get("pack_id") if pack else None}})
        if args.export_pack:
            result["pack_manifest"] = store.export_pack(portfolio_id, {"profile": args.profile})
        if args.zip_pack:
            result["pack_zip"] = store.build_pack_zip(portfolio_id, {"profile": args.profile})
        if args.verify_pack:
            report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(
                store.pack_zip_path(portfolio_id, args.profile),
                strict=args.strict,
                require_pack=True,
                require_transparency=args.require_transparency,
            )
            write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report, store.pack_verification_report_path(portfolio_id, args.profile))
            result["pack_verification"] = report
        if args.import_response:
            payload: dict[str, Any] = {"profile": args.profile}
            if args.content_base64:
                payload["content_base64"] = args.content_base64
            imported = store.import_response(portfolio_id, payload)
            result.update(imported)
        if args.refresh_evidence:
            payload = {"profile": args.profile}
            if args.response_id:
                payload["response_id"] = args.response_id
            evidence = store.refresh_evidence(portfolio_id, payload)
            result.update({"acknowledgement_evidence": evidence, "evidence_summary": acknowledgement_summary(evidence)})
        if args.export_evidence:
            result["evidence_manifest"] = store.export_evidence(portfolio_id, {"profile": args.profile})
        if args.zip_evidence:
            result["evidence_zip"] = store.build_evidence_zip(portfolio_id, {"profile": args.profile})
        if args.verify_evidence:
            report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(
                store.evidence_zip_path(portfolio_id, args.profile),
                strict=args.strict,
                require_response=True,
                require_accepted=args.require_accepted,
            )
            write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report, store.evidence_verification_report_path(portfolio_id, args.profile))
            result["evidence_verification"] = report
        if args.create_change_request:
            if not args.response_id:
                raise SystemExit("--response-id is required with --create-change-request")
            result["change_request"] = store.create_change_request(portfolio_id, args.response_id, {"profile": args.profile})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_portfolio_governance_attestation_transparency_acknowledgement_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "public-trust-center-publication":
        from song_agent.public_trust_center_publication import PublicTrustCenterPublicationStore, publication_summary
        from song_agent.public_trust_center_publication_verifier import (
            print_public_trust_center_publication_verification_report,
        )

        parser = build_public_trust_center_publication_parser()
        args = parser.parse_args(raw_args[1:])
        trust_store = _build_public_trust_center_store()
        from song_agent.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStore
        from song_agent.public_trust_center_anchor_transparency import PublicTrustCenterAnchorTransparencyStore
        from song_agent.public_trust_center_distribution_kit import PublicTrustCenterDistributionKitStore
        from song_agent.public_trust_center_distribution_kit_acceptance import PublicTrustCenterDistributionKitAcceptanceStore
        from song_agent.public_trust_center_acceptance_board import PublicTrustCenterAcceptanceBoardStore

        anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=trust_store)
        anchor_transparency_store = PublicTrustCenterAnchorTransparencyStore(anchor_registry_store=anchor_store)
        distribution_kit_store = PublicTrustCenterDistributionKitStore(trust_center_store=trust_store, anchor_registry_store=anchor_store, anchor_transparency_store=anchor_transparency_store)
        acceptance_store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=distribution_kit_store)
        board_store = PublicTrustCenterAcceptanceBoardStore(acceptance_store=acceptance_store)
        store = PublicTrustCenterPublicationStore(
            trust_center_store=trust_store,
            distribution_kit_store=distribution_kit_store,
            anchor_registry_store=anchor_store,
            anchor_transparency_store=anchor_transparency_store,
            acceptance_store=acceptance_store,
            acceptance_board_store=board_store,
        )
        result: dict[str, Any] = {"ok": True, "center_id": args.center_id, "channel_id": args.channel_id}
        if args.create_channel:
            result["channel"] = store.create_channel(args.center_id, {"channel_id": args.channel_id, "name": args.channel_name, "channel_type": args.channel_type})
        else:
            try:
                result["channel"] = store.read_channel(args.center_id, args.channel_id)
            except Exception:
                result["channel"] = store.create_channel(args.center_id, {"channel_id": args.channel_id, "name": args.channel_name, "channel_type": args.channel_type})
        publication_id = args.publication_id
        if args.refresh:
            report = store.refresh_publication(args.center_id, args.channel_id)
            publication_id = str(report.get("publication_id") or publication_id or "")
            result["publication"] = report
            result["summary"] = publication_summary(report)
        if args.supersede:
            report = store.supersede_publication(args.center_id, args.channel_id, publication_id, {"reason": args.reason})
            publication_id = str(report.get("publication_id") or publication_id or "")
            result["publication"] = report
            result["summary"] = publication_summary(report)
        if args.revoke:
            if not publication_id:
                publication_id = store._current_publication_id(args.center_id, args.channel_id)
            report = store.revoke_publication(args.center_id, args.channel_id, publication_id, {"reason": args.reason})
            result["publication"] = report
            result["summary"] = publication_summary(report)
        if args.export:
            result["manifest"] = store.export_publication(args.center_id, args.channel_id, publication_id)
            publication_id = str(result["manifest"].get("publication_id") or publication_id or "")
        if args.zip:
            result["zip"] = store.build_publication_zip(args.center_id, args.channel_id, publication_id)
            publication_id = str(result["zip"].get("publication_id") or publication_id or "")
        if args.verify:
            verification = store.verify_publication_zip(
                args.center_id,
                args.channel_id,
                publication_id,
                {
                    "strict": args.strict,
                    "deep": args.deep,
                    "require_ready": args.require_ready,
                    "require_acceptance_board_signoff": args.require_acceptance_board_signoff,
                    "require_anchor_current": args.require_anchor_current,
                    "require_no_revoked": args.require_no_revoked,
                    "publication_channel_state_path": args.publication_channel_state,
                },
            )
            result["verification"] = verification
            result["verification_summary"] = verification.get("summary", {})
        if args.verify_mirror:
            if not publication_id:
                publication_id = store._current_publication_id(args.center_id, args.channel_id)
            mirror_dir = args.mirror_dir or store.export_dir(args.center_id, args.channel_id, publication_id)
            verification = store.verify_mirror_directory(
                args.center_id,
                args.channel_id,
                publication_id,
                mirror_dir,
                {
                    "strict": args.strict,
                    "require_ready": args.require_ready,
                    "require_acceptance_board_signoff": args.require_acceptance_board_signoff,
                    "require_anchor_current": args.require_anchor_current,
                    "require_no_revoked": args.require_no_revoked,
                    "publication_channel_state_path": args.publication_channel_state,
                },
            )
            result["mirror_verification"] = verification
            result["mirror_verification_summary"] = verification.get("summary", {})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if "verification" in result:
                print_public_trust_center_publication_verification_report(result["verification"])
            elif "mirror_verification" in result:
                print_public_trust_center_publication_verification_report(result["mirror_verification"])
            else:
                print(json.dumps(result.get("summary") or {"status": "ok"}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "public-trust-center-publication-monitor":
        from song_agent.public_trust_center_publication_monitoring import PublicTrustCenterPublicationMonitoringStore, monitoring_summary
        from song_agent.public_trust_center_publication_monitoring_verifier import print_public_trust_center_publication_monitoring_verification_report

        parser = build_public_trust_center_publication_monitor_parser()
        args = parser.parse_args(raw_args[1:])
        publication_store = _build_public_trust_center_publication_store()
        store = PublicTrustCenterPublicationMonitoringStore(publication_store=publication_store)
        result: dict[str, Any] = {"ok": True, "center_id": args.center_id, "channel_id": args.channel_id}
        monitor_id = args.monitor_id
        if args.create_monitor:
            monitor = store.create_monitor(args.center_id, args.channel_id, {"monitor_id": monitor_id, "name": args.monitor_name, "publication_id": args.publication_id, "mirror_dir": args.mirror_dir})
            monitor_id = str(monitor.get("monitor_id") or monitor_id or "")
            result["monitor"] = monitor
        elif monitor_id:
            result["monitor"] = store.read_monitor(args.center_id, args.channel_id, monitor_id)
        else:
            monitors = store.list_monitors(args.center_id, args.channel_id)
            if monitors:
                monitor_id = str(monitors[0].get("monitor_id") or "")
                result["monitor"] = monitors[0]
            else:
                monitor = store.create_monitor(args.center_id, args.channel_id, {"name": args.monitor_name, "publication_id": args.publication_id, "mirror_dir": args.mirror_dir})
                monitor_id = str(monitor.get("monitor_id") or "")
                result["monitor"] = monitor
        if not monitor_id:
            raise ValueError("--monitor-id is required.")
        run_id = args.run_id
        if args.run:
            run_result = store.run_monitor(args.center_id, args.channel_id, monitor_id, {"publication_id": args.publication_id, "mirror_dir": args.mirror_dir, "publication_channel_state_path": args.publication_channel_state})
            run_id = str((run_result.get("monitor_run") or {}).get("run_id") or run_id or "")
            result.update(run_result)
            result["summary"] = monitoring_summary(run_result.get("monitor_run") or {})
        if args.ack_incident:
            result["incident"] = store.acknowledge_incident(args.center_id, args.channel_id, monitor_id, args.ack_incident, {"reason": args.reason})
        if args.resolve_incident:
            result["incident"] = store.resolve_incident(args.center_id, args.channel_id, monitor_id, args.resolve_incident, {"resolution_note": args.reason})
        if args.waive_incident:
            result["incident"] = store.waive_incident(args.center_id, args.channel_id, monitor_id, args.waive_incident, {"waiver_reason": args.reason})
        if args.reopen_incident:
            result["incident"] = store.reopen_incident(args.center_id, args.channel_id, monitor_id, args.reopen_incident, {"reason": args.reason})
        if args.export:
            if not run_id:
                raise ValueError("--run-id is required for --export unless --run was used.")
            result["manifest"] = store.export_monitoring_run(args.center_id, args.channel_id, monitor_id, run_id)
        if args.zip:
            if not run_id:
                raise ValueError("--run-id is required for --zip unless --run was used.")
            result["zip"] = store.build_monitoring_zip(args.center_id, args.channel_id, monitor_id, run_id)
        if args.verify:
            if not run_id:
                raise ValueError("--run-id is required for --verify unless --run was used.")
            verification = store.verify_monitoring_zip(
                args.center_id,
                args.channel_id,
                monitor_id,
                run_id,
                {
                    "strict": args.strict,
                    "require_current": args.require_current,
                    "require_no_revoked": args.require_no_revoked,
                    "require_ready": args.require_ready,
                    "require_no_drift": args.require_no_drift,
                    "require_no_open_critical_incidents": args.require_no_open_critical_incidents,
                    "allow_waived_incidents": args.allow_waived_incidents,
                    "publication_channel_state_path": args.publication_channel_state,
                },
            )
            result["verification"] = verification
            result["verification_summary"] = verification.get("summary", {})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if "verification" in result:
                print_public_trust_center_publication_monitoring_verification_report(result["verification"])
            else:
                print(json.dumps(result.get("summary") or {"status": "ok"}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "trust-operations-hub":
        from song_agent.trust_operations_hub import TrustOperationsHubStore
        from song_agent.trust_operations_hub_verifier import print_trust_operations_hub_verification_report

        parser = build_trust_operations_hub_parser()
        args = parser.parse_args(raw_args[1:])
        store = TrustOperationsHubStore()
        result: dict[str, Any] = {"ok": True}
        hub_id = args.hub_id
        if args.create or not hub_id:
            if hub_id and store.hub_path(hub_id).exists():
                hub = store.read_hub(hub_id)
            else:
                hub = store.create_hub({"hub_id": hub_id, "name": args.name})
            hub_id = str(hub.get("hub_id") or hub_id or "")
            result["hub"] = hub
        if not hub_id:
            hubs = store.list_hubs()
            if not hubs:
                hub = store.create_hub({"name": args.name})
                hubs = [hub]
            hub_id = str(hubs[0].get("hub_id") or "")
            result["hub"] = hubs[0]
        if not hub_id:
            raise ValueError("--hub-id is required.")
        report_id = args.report_id
        source_payload = {
            "publication_channel_state_path": args.publication_channel_state,
            "public_trust_center_verification_path": args.public_trust_center_verification,
            "publication_monitoring_verification_path": args.publication_monitoring_verification,
            "release_verification_paths": args.release_verification,
            "distribution_verification_paths": args.distribution_verification,
            "submission_verification_paths": args.submission_verification,
            "submission_evidence_verification_paths": args.submission_evidence_verification,
            "release_operations_verification_paths": args.release_operations_verification,
        }
        if args.refresh:
            refreshed = store.refresh_report(hub_id, source_payload)
            report_id = str((refreshed.get("hub_report") or {}).get("report_id") or report_id or "")
            result.update(refreshed)
        if not report_id:
            current = read_json(store.current_report_path(hub_id)) if store.current_report_path(hub_id).exists() else {}
            report_id = str(current.get("report_id") or "")
        if args.create_change_request:
            result["change_request"] = store.create_change_request(hub_id, {"reason": args.reason, "change_request_id": args.change_request_id})
        if args.approve_change_request:
            result["change_request"] = store.approve_change_request(hub_id, args.approve_change_request)
        if args.reset_signoff:
            if not args.change_request_id:
                raise ValueError("--change-request-id is required for --reset-signoff.")
            result["reset"] = store.reset_signoff(hub_id, args.change_request_id)
        if args.export:
            if not report_id:
                raise ValueError("--report-id is required for --export unless --refresh was used.")
            result["manifest"] = store.export_report(hub_id, report_id)
        if args.zip:
            if not report_id:
                raise ValueError("--report-id is required for --zip unless --refresh was used.")
            result["zip"] = store.build_zip(hub_id, report_id)
        if args.verify:
            if not report_id:
                raise ValueError("--report-id is required for --verify unless --refresh was used.")
            verification = store.verify_zip(
                hub_id,
                report_id,
                {
                    "strict": args.strict,
                    "require_ready": args.require_ready,
                    "require_signed": args.require_signed,
                    "require_current": args.require_current,
                    "require_no_critical_blockers": args.require_no_critical_blockers,
                    "require_publication_monitoring_clean": args.require_publication_monitoring_clean,
                    "require_delivery_ready": args.require_delivery_ready,
                    "require_incident_closeout": args.require_incident_closeout,
                    "require_incident_regression_guards": args.require_incident_regression_guards,
                    "require_trust_controls": args.require_trust_controls,
                    "require_trust_control_signoff": args.require_trust_control_signoff,
                    "require_continuous_assurance": args.require_continuous_assurance,
                    "publication_channel_state_path": args.publication_channel_state,
                    "public_trust_center_verification_path": args.public_trust_center_verification,
                    "publication_monitoring_verification_path": args.publication_monitoring_verification,
                    "release_verification_paths": args.release_verification,
                    "distribution_verification_paths": args.distribution_verification,
                    "submission_verification_paths": args.submission_verification,
                    "submission_evidence_verification_paths": args.submission_evidence_verification,
                    "release_operations_verification_paths": args.release_operations_verification,
                    "hub_signoff_path": args.hub_signoff,
                    "hub_verification_report_path": args.hub_verification_report,
                    "incident_board_package_path": args.incident_board_package,
                    "incident_board_verification_report_path": args.incident_board_verification_report,
                    "incident_knowledge_package_path": args.incident_knowledge_package,
                    "incident_knowledge_verification_report_path": args.incident_knowledge_verification_report,
                    "trust_control_package_path": args.trust_control_package,
                    "trust_control_verification_report_path": args.trust_control_verification_report,
                    "trust_control_signoff_archive_path": args.trust_control_signoff_archive,
                    "trust_control_signoff_verification_report_path": args.trust_control_signoff_verification_report,
                    "continuous_assurance_archive_path": args.continuous_assurance_archive,
                    "continuous_assurance_verification_report_path": args.continuous_assurance_verification_report,
                    "require_assurance_watch_clear": args.require_assurance_watch_clear,
                    "assurance_watch_package_path": args.assurance_watch_package,
                    "assurance_watch_verification_report_path": args.assurance_watch_verification_report,
                    "require_assurance_watch_signoff": args.require_assurance_watch_signoff,
                    "assurance_watch_signoff_archive_path": args.assurance_watch_signoff_archive,
                    "assurance_watch_signoff_verification_report_path": args.assurance_watch_signoff_verification_report,
                },
            )
            result["verification"] = verification
            result["verification_summary"] = verification.get("summary", {})
        if args.signoff:
            if not report_id:
                raise ValueError("--report-id is required for --signoff unless --refresh was used.")
            result["signoff"] = store.signoff(hub_id, report_id, {"signed_by": args.signed_by, "reason": args.reason, "force": args.force, "override_reason": args.override_reason})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if "verification" in result:
                print_trust_operations_hub_verification_report(result["verification"])
            else:
                print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": hub_id, "report_id": report_id}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "trust-operations-assurance-watch":
        from song_agent.trust_operations_assurance_watch import TrustOperationsAssuranceWatchStore
        from song_agent.trust_operations_assurance_watch_verifier import print_trust_operations_assurance_watch_verification_report
        from song_agent.trust_operations_continuous_assurance import TrustOperationsAssuranceStore
        from song_agent.trust_operations_hub import TrustOperationsHubStore

        parser = build_trust_operations_assurance_watch_parser()
        args = parser.parse_args(raw_args[1:])
        hub_store = TrustOperationsHubStore()
        assurance_store = TrustOperationsAssuranceStore(hub_store=hub_store)
        store = TrustOperationsAssuranceWatchStore(assurance_store=assurance_store, hub_store=hub_store)
        result: dict[str, Any] = {"ok": True, "schedule_id": args.schedule_id}
        source_payload = _trust_operations_assurance_watch_source_payload(args)
        schedule_patch: dict[str, Any] = {}
        if args.hub_id:
            schedule_patch.setdefault("scope", {})["hub_ids"] = [args.hub_id]
        if args.interval_days is not None or args.grace_days is not None:
            schedule_patch.setdefault("cadence", {})
            if args.interval_days is not None:
                schedule_patch["cadence"]["interval_days"] = args.interval_days
            if args.grace_days is not None:
                schedule_patch["cadence"]["grace_days"] = args.grace_days
        if args.write_schedule:
            result["schedule"] = store.write_schedule({"schedule_id": args.schedule_id, **schedule_patch})
        if args.list:
            result["queues"] = store.list_queues(args.schedule_id)
        if args.refresh:
            refresh_payload: dict[str, Any] = {**source_payload}
            if args.queue_id:
                refresh_payload["queue_id"] = args.queue_id
            if args.hub_id:
                refresh_payload["hub_id"] = args.hub_id
            refreshed = store.refresh_queue(refresh_payload, schedule_id=args.schedule_id)
            result.update(refreshed)
            args.queue_id = str((refreshed.get("queue") or {}).get("queue_id") or args.queue_id or "")
        if args.export:
            if not args.queue_id:
                raise ValueError("--queue-id is required for --export unless --refresh was used.")
            result["manifest"] = store.export_watch(args.queue_id, source_payload)
        if args.zip:
            if not args.queue_id:
                raise ValueError("--queue-id is required for --zip unless --refresh was used.")
            result["zip"] = store.build_watch_zip(args.queue_id, source_payload)
        if args.verify:
            if not args.queue_id:
                raise ValueError("--queue-id is required for --verify unless --refresh was used.")
            verification = store.verify_watch_zip(args.queue_id, {**source_payload, "strict": args.strict, "require_clear": args.require_clear, "require_current": args.require_current})
            result["verification"] = verification
            result["verification_summary"] = verification.get("summary", {})
        if not any([args.write_schedule, args.list, args.refresh, args.export, args.zip, args.verify]):
            result["summary"] = store.summary(args.queue_id) if args.queue_id else {"schedule": store.read_schedule(args.schedule_id), "queues": store.list_queues(args.schedule_id)}
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if "verification" in result:
                print_trust_operations_assurance_watch_verification_report(result["verification"])
            else:
                print(json.dumps(result.get("summary") or {"status": "ok", "queue_id": args.queue_id}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "trust-operations-assurance-watch-signoff":
        from song_agent.trust_operations_assurance_watch import TrustOperationsAssuranceWatchStore
        from song_agent.trust_operations_assurance_watch_signoff import TrustOperationsAssuranceWatchSignoffStore
        from song_agent.trust_operations_assurance_watch_signoff_verifier import print_trust_operations_assurance_watch_signoff_verification_report
        from song_agent.trust_operations_continuous_assurance import TrustOperationsAssuranceStore
        from song_agent.trust_operations_hub import TrustOperationsHubStore

        parser = build_trust_operations_assurance_watch_signoff_parser()
        args = parser.parse_args(raw_args[1:])
        hub_store = TrustOperationsHubStore()
        assurance_store = TrustOperationsAssuranceStore(hub_store=hub_store)
        watch_store = TrustOperationsAssuranceWatchStore(assurance_store=assurance_store, hub_store=hub_store)
        store = TrustOperationsAssuranceWatchSignoffStore(watch_store=watch_store, assurance_store=assurance_store, hub_store=hub_store)
        result: dict[str, Any] = {"ok": True, "queue_id": args.queue_id}
        source_payload = {
            "watch_package_path": args.watch_package,
            "watch_verification_report_path": args.watch_verification_report,
            "hub_package_path": args.hub_package,
            "hub_verification_report_path": args.hub_verification_report,
            "continuous_assurance_report_path": args.continuous_assurance_report,
        }
        if args.refresh_closeout:
            result["closeout"] = store.refresh_closeout(args.queue_id, source_payload)
        if args.sign:
            result["signoff"] = store.sign(args.queue_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        if args.create_change_request:
            result["change_request"] = store.create_change_request(args.queue_id, {"reason": args.reason, "requested_by": args.signed_by})
        if args.approve_change_request:
            result["change_request"] = store.approve_change_request(args.queue_id, args.approve_change_request, {"approved_by": args.signed_by})
        if args.reset_signoff:
            result["reset"] = store.reset_signoff(args.queue_id, args.reset_signoff)
        if args.export:
            result["manifest"] = store.export_archive(args.queue_id, source_payload)
        if args.zip:
            result["zip"] = store.build_archive_zip(args.queue_id)
        if args.verify:
            verification = store.verify_archive_zip(args.queue_id, {**source_payload, "strict": args.strict, "require_signed": args.require_signed, "require_current": args.require_current})
            result["verification"] = verification
            result["verification_summary"] = verification.get("summary", {})
        if not any([args.refresh_closeout, args.sign, args.create_change_request, args.approve_change_request, args.reset_signoff, args.export, args.zip, args.verify]):
            result["summary"] = store.summary(args.queue_id)
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if "verification" in result:
                print_trust_operations_assurance_watch_signoff_verification_report(result["verification"])
            else:
                print(json.dumps(result.get("summary") or {"status": "ok", "queue_id": args.queue_id}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "trust-operations-final-readiness":
        from song_agent.trust_operations_final_readiness import TrustOperationsFinalReadinessStore
        from song_agent.trust_operations_final_readiness_verifier import print_trust_operations_final_handoff_verification_report

        parser = build_trust_operations_final_readiness_parser()
        args = parser.parse_args(raw_args[1:])
        store = TrustOperationsFinalReadinessStore()
        result: dict[str, Any] = {"ok": True}
        source_payload = _trust_operations_final_readiness_source_payload(args)
        if args.refresh_report:
            result.update(store.refresh_report(source_payload))
        if args.create_certificate:
            result["certificate"] = store.create_certificate()
        if args.sign:
            result["signoff"] = store.sign({"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        if args.create_change_request:
            result["change_request"] = store.create_change_request({"reason": args.reason, "requested_by": args.signed_by})
        if args.approve_change_request:
            result["change_request"] = store.approve_change_request(args.approve_change_request, {"approved_by": args.signed_by})
        if args.reset_signoff:
            result["reset"] = store.reset_signoff(args.reset_signoff)
        if args.export:
            result["manifest"] = store.export_handoff(source_payload)
        if args.zip:
            result["zip"] = store.build_handoff_zip()
        if args.verify:
            verification = store.verify_handoff_zip({**source_payload, "strict": args.strict, "require_signed": args.require_signed, "require_current": args.require_current})
            result["verification"] = verification
            result["verification_summary"] = verification.get("summary", {})
        if not any([args.refresh_report, args.create_certificate, args.sign, args.create_change_request, args.approve_change_request, args.reset_signoff, args.export, args.zip, args.verify]):
            result["summary"] = store.summary()
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if "verification" in result:
                print_trust_operations_final_handoff_verification_report(result["verification"])
            else:
                print(json.dumps(result.get("summary") or {"status": "ok"}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "trust-operations-controls":
        from song_agent.trust_operations_controls import TrustOperationsControlStore
        from song_agent.trust_operations_controls_verifier import print_trust_operations_control_verification_report
        from song_agent.trust_operations_hub import TrustOperationsHubStore
        from song_agent.trust_operations_hub_incidents import TrustOperationsIncidentStore
        from song_agent.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore

        parser = build_trust_operations_controls_parser()
        args = parser.parse_args(raw_args[1:])
        hub_store = TrustOperationsHubStore()
        incident_store = TrustOperationsIncidentStore(hub_store=hub_store)
        knowledge_store = TrustOperationsIncidentKnowledgeStore(hub_store=hub_store, incident_store=incident_store)
        store = TrustOperationsControlStore(hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
        result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
        source_payload = {
            "hub_package_path": args.hub_package,
            "hub_verification_report_path": args.hub_verification_report,
            "incident_board_package_path": args.incident_board_package,
            "incident_board_verification_report_path": args.incident_board_verification_report,
            "incident_knowledge_package_path": args.incident_knowledge_package,
            "incident_knowledge_verification_report_path": args.incident_knowledge_verification_report,
        }
        if args.refresh_catalog:
            result["catalog"] = store.refresh_catalog(args.hub_id, source_payload)
        if args.create_policy:
            policy = store.create_policy_bundle(args.hub_id, {"policy_id": args.policy_id, "name": args.policy_name})
            args.policy_id = str(policy.get("policy_id") or args.policy_id or "")
            result["policy"] = policy
        if args.assess:
            if not args.policy_id:
                policies = store.list_policies(args.hub_id)
                if not policies:
                    raise ValueError("--policy-id is required when no policy exists.")
                args.policy_id = str(policies[0].get("policy_id") or "")
            assessed = store.assess_policy(args.hub_id, str(args.policy_id), {**source_payload, "assessment_id": args.assessment_id})
            args.assessment_id = str((assessed.get("assessment") or {}).get("assessment_id") or args.assessment_id or "")
            result.update(assessed)
        if not args.assessment_id and (args.export or args.zip or args.verify):
            assessments = sorted(store.assessments_dir(args.hub_id).glob("*/control-assessment-report.json")) if store.assessments_dir(args.hub_id).exists() else []
            if assessments:
                args.assessment_id = assessments[-1].parent.name
        if args.export:
            if not args.assessment_id:
                raise ValueError("--assessment-id is required for --export unless --assess was used.")
            result["manifest"] = store.export_controls(args.hub_id, str(args.assessment_id))
        if args.zip:
            if not args.assessment_id:
                raise ValueError("--assessment-id is required for --zip unless --assess was used.")
            result["zip"] = store.build_zip(args.hub_id, str(args.assessment_id))
        if args.verify:
            if not args.assessment_id:
                raise ValueError("--assessment-id is required for --verify unless --assess was used.")
            verification = store.verify_zip(args.hub_id, str(args.assessment_id), {**source_payload, "strict": args.strict, "require_policy_passed": args.require_policy_passed})
            result["verification"] = verification
            result["verification_summary"] = verification.get("summary", {})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if "verification" in result:
                print_trust_operations_control_verification_report(result["verification"])
            else:
                print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id, "assessment_id": args.assessment_id}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "trust-operations-assurance":
        from song_agent.trust_operations_continuous_assurance import TrustOperationsAssuranceStore
        from song_agent.trust_operations_continuous_assurance_verifier import print_trust_operations_assurance_verification_report
        from song_agent.trust_operations_hub import TrustOperationsHubStore

        parser = build_trust_operations_assurance_parser()
        args = parser.parse_args(raw_args[1:])
        hub_store = TrustOperationsHubStore()
        store = TrustOperationsAssuranceStore(hub_store=hub_store)
        result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
        source_payload = _trust_operations_assurance_source_payload(args)
        if args.list:
            result["runs"] = store.list_runs(args.hub_id)
        if args.refresh:
            refreshed = store.refresh_run(args.hub_id, {**source_payload, "run_id": args.run_id}, policy_id=args.policy_id)
            result.update(refreshed)
            args.run_id = str((refreshed.get("run") or {}).get("run_id") or args.run_id or "")
        if args.export:
            if not args.run_id:
                raise ValueError("--run-id is required for --export unless --refresh was used.")
            result["manifest"] = store.export_archive(args.run_id, source_payload)
        if args.zip:
            if not args.run_id:
                raise ValueError("--run-id is required for --zip unless --refresh was used.")
            result["zip"] = store.build_archive_zip(args.run_id, source_payload)
        if args.verify:
            if not args.run_id:
                raise ValueError("--run-id is required for --verify unless --refresh was used.")
            verification = store.verify_archive_zip(args.run_id, {**source_payload, "strict": args.strict, "require_passed": args.require_passed, "require_current": args.require_current})
            result["verification"] = verification
            result["verification_summary"] = verification.get("summary", {})
        if not any([args.list, args.refresh, args.export, args.zip, args.verify]):
            if not args.run_id:
                result["runs"] = store.list_runs(args.hub_id)
            else:
                result["summary"] = store.summary(args.run_id)
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if "verification" in result:
                print_trust_operations_assurance_verification_report(result["verification"])
            else:
                print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id, "run_id": args.run_id}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "trust-operations-control-signoff":
        from song_agent.trust_operations_control_signoff import TrustOperationsControlSignoffStore
        from song_agent.trust_operations_control_signoff_verifier import print_trust_operations_control_signoff_verification_report
        from song_agent.trust_operations_controls import TrustOperationsControlStore
        from song_agent.trust_operations_hub import TrustOperationsHubStore
        from song_agent.trust_operations_hub_incidents import TrustOperationsIncidentStore
        from song_agent.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore

        parser = build_trust_operations_control_signoff_parser()
        args = parser.parse_args(raw_args[1:])
        hub_store = TrustOperationsHubStore()
        incident_store = TrustOperationsIncidentStore(hub_store=hub_store)
        knowledge_store = TrustOperationsIncidentKnowledgeStore(hub_store=hub_store, incident_store=incident_store)
        control_store = TrustOperationsControlStore(hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
        store = TrustOperationsControlSignoffStore(control_store=control_store, hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
        result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
        source_payload = {
            "control_package_path": args.control_package,
            "control_verification_report_path": args.control_verification_report,
            "hub_package_path": args.hub_package,
            "hub_verification_report_path": args.hub_verification_report,
            "incident_board_package_path": args.incident_board_package,
            "incident_board_verification_report_path": args.incident_board_verification_report,
            "incident_knowledge_package_path": args.incident_knowledge_package,
            "incident_knowledge_verification_report_path": args.incident_knowledge_verification_report,
        }
        if args.sign:
            if not args.assessment_id:
                raise ValueError("--assessment-id is required for --sign.")
            result["signoff"] = store.sign(args.hub_id, str(args.assessment_id), {**source_payload, "signed_by": args.signed_by, "reason": args.reason})
        if args.request_exception:
            if not args.assessment_id or not args.control_id:
                raise ValueError("--assessment-id and --control-id are required for --request-exception.")
            result["exception"] = store.request_exception(args.hub_id, {"assessment_id": args.assessment_id, "control_id": args.control_id, "requested_by": args.requested_by, "reason": args.reason, "expires_at": args.expires_at, "mitigation": args.mitigation})
        if args.approve_exception:
            if not args.exception_id:
                raise ValueError("--exception-id is required for --approve-exception.")
            result["exception"] = store.approve_exception(args.hub_id, args.exception_id, {"approved_by": args.approved_by, "reason": args.reason})
        if args.reject_exception:
            if not args.exception_id:
                raise ValueError("--exception-id is required for --reject-exception.")
            result["exception"] = store.reject_exception(args.hub_id, args.exception_id, {"approved_by": args.approved_by, "reason": args.reason})
        if args.create_change_request:
            result["change_request"] = store.create_change_request(args.hub_id, {"reason": args.reason, "created_by": args.requested_by, "change_request_id": args.change_request_id})
        if args.approve_change_request:
            if not args.change_request_id:
                raise ValueError("--change-request-id is required for --approve-change-request.")
            result["change_request"] = store.approve_change_request(args.hub_id, args.change_request_id, {"approved_by": args.approved_by, "reason": args.reason})
        if args.reset:
            if not args.change_request_id:
                raise ValueError("--change-request-id is required for --reset.")
            result["reset"] = store.reset_signoff(args.hub_id, args.change_request_id)
        if args.export:
            result["manifest"] = store.export_archive(args.hub_id, source_payload)
        if args.zip:
            result["zip"] = store.build_archive_zip(args.hub_id)
        if args.verify:
            verification = store.verify_archive_zip(args.hub_id, {**source_payload, "strict": args.strict, "require_signed": args.require_signed, "require_current": args.require_current})
            result["verification"] = verification
            result["verification_summary"] = verification.get("summary", {})
        if not any([args.sign, args.request_exception, args.approve_exception, args.reject_exception, args.create_change_request, args.approve_change_request, args.reset, args.export, args.zip, args.verify]):
            result["summary"] = store.summary(args.hub_id)
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if "verification" in result:
                print_trust_operations_control_signoff_verification_report(result["verification"])
            else:
                print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "trust-operations-hub-runbook":
        from song_agent.trust_operations_hub import TrustOperationsHubStore
        from song_agent.trust_operations_hub_runbook import TrustOperationsHubRunbookStore
        from song_agent.trust_operations_hub_runbook_verifier import print_trust_operations_hub_runbook_verification_report, verify_trust_operations_hub_runbook_package

        parser = build_trust_operations_hub_runbook_parser()
        args = parser.parse_args(raw_args[1:])
        hub_store = TrustOperationsHubStore()
        store = TrustOperationsHubRunbookStore(hub_store=hub_store)
        result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
        report_id = args.report_id
        if not report_id:
            current = read_json(hub_store.current_report_path(args.hub_id)) if hub_store.current_report_path(args.hub_id).exists() else {}
            report_id = str(current.get("report_id") or "")
        runbook_id = args.runbook_id
        if args.create:
            if not report_id:
                raise ValueError("--report-id is required for --create unless a current Hub report exists.")
            runbook = store.create_runbook(args.hub_id, report_id, {"runbook_id": runbook_id})
            runbook_id = str(runbook.get("runbook_id") or runbook_id or "")
            result["runbook"] = runbook
        if not runbook_id:
            raise ValueError("--runbook-id is required unless --create was used.")
        if args.run_safe:
            result["result"] = store.run_safe_actions(args.hub_id, runbook_id)
        if args.export:
            result["manifest"] = store.export_runbook(args.hub_id, runbook_id)
        if args.zip:
            result["zip"] = store.build_zip(args.hub_id, runbook_id)
        if args.verify:
            verification = verify_trust_operations_hub_runbook_package(store.zip_path(args.hub_id, runbook_id), strict=args.strict, require_completed=args.require_completed, require_no_blocked=args.require_no_blocked)
            result["verification"] = verification
            result["verification_summary"] = verification.get("summary", {})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if "verification" in result:
                print_trust_operations_hub_runbook_verification_report(result["verification"])
            else:
                print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id, "runbook_id": runbook_id}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "trust-operations-hub-incidents":
        import base64

        from song_agent.trust_operations_hub import TrustOperationsHubStore
        from song_agent.trust_operations_hub_incident_verifier import print_trust_operations_hub_incident_verification_report
        from song_agent.trust_operations_hub_incidents import TrustOperationsIncidentStore

        parser = build_trust_operations_hub_incidents_parser()
        args = parser.parse_args(raw_args[1:])
        hub_store = TrustOperationsHubStore()
        store = TrustOperationsIncidentStore(hub_store=hub_store)
        result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
        incident_id = args.incident_id
        if args.refresh:
            refreshed = store.refresh_board(args.hub_id, {"report_id": args.report_id} if args.report_id else {})
            result.update(refreshed)
        if args.list:
            result["incidents"] = store.list_incidents(args.hub_id)
        if any([args.triage, args.create_plan, args.add_evidence, args.verify_fix, args.close, args.archive]) and not incident_id:
            incidents = store.list_incidents(args.hub_id)
            if not incidents:
                raise ValueError("--incident-id is required when no incidents exist.")
            incident_id = str(incidents[0].get("incident_id") or "")
        if args.triage:
            result["incident"] = store.triage_incident(args.hub_id, str(incident_id), {"severity": args.severity, "owner": args.owner, "notes": args.notes})
        if args.create_plan:
            result["plan"] = store.create_plan(args.hub_id, str(incident_id))
        if args.add_evidence:
            content_base64 = args.content_base64
            if args.evidence_file is not None:
                content_base64 = base64.b64encode(args.evidence_file.read_bytes()).decode("ascii")
            result["evidence"] = store.add_evidence(
                args.hub_id,
                str(incident_id),
                {
                    "kind": args.evidence_kind,
                    "component_type": args.component_type,
                    "component_id": args.component_id,
                    "content_base64": content_base64,
                },
            )
        if args.verify_fix:
            result["fix_verification"] = store.verify_fix(args.hub_id, str(incident_id))
        if args.close:
            result["closeout"] = store.close_incident(args.hub_id, str(incident_id), {"closed_by": args.closed_by, "reason": args.reason})
        if args.archive:
            result["incident"] = store.archive_incident(args.hub_id, str(incident_id))
        if args.export:
            result["manifest"] = store.export_board(args.hub_id)
        if args.zip:
            result["zip"] = store.build_zip(args.hub_id)
        if args.verify:
            verification = store.verify_zip(
                args.hub_id,
                {
                    "strict": args.strict,
                    "require_no_open_critical": args.require_no_open_critical,
                    "require_no_open_blocking": args.require_no_open_blocking,
                    "require_current_hub": args.require_current_hub,
                    "hub_verification_report_path": args.hub_verification_report,
                },
            )
            result["verification"] = verification
            result["verification_summary"] = verification.get("summary", {})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if "verification" in result:
                print_trust_operations_hub_incident_verification_report(result["verification"])
            else:
                print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id, "incident_id": incident_id}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "trust-operations-incident-knowledge":
        from song_agent.trust_operations_hub import TrustOperationsHubStore
        from song_agent.trust_operations_hub_incidents import TrustOperationsIncidentStore
        from song_agent.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore
        from song_agent.trust_operations_incident_knowledge_verifier import print_trust_operations_incident_knowledge_verification_report

        parser = build_trust_operations_incident_knowledge_parser()
        args = parser.parse_args(raw_args[1:])
        hub_store = TrustOperationsHubStore()
        incident_store = TrustOperationsIncidentStore(hub_store=hub_store)
        store = TrustOperationsIncidentKnowledgeStore(hub_store=hub_store, incident_store=incident_store)
        result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
        if args.refresh:
            result.update(store.refresh(args.hub_id, {"incident_board_verification_report_path": args.incident_board_verification_report, "hub_verification_report_path": args.hub_verification_report}))
        if args.list_entries:
            result["entries"] = store.list_entries(args.hub_id)
        if any([args.hide_entry, args.unhide_entry, args.create_guard]) and not args.entry_id:
            entries = store.list_entries(args.hub_id)
            if not entries:
                raise ValueError("--entry-id is required when no entries exist.")
            args.entry_id = str(entries[0].get("entry_id") or "")
        if args.hide_entry:
            result["entry"] = store.hide_entry(args.hub_id, str(args.entry_id))
        if args.unhide_entry:
            result["entry"] = store.unhide_entry(args.hub_id, str(args.entry_id))
        if args.create_guard:
            result["guard"] = store.create_guard(args.hub_id, str(args.entry_id), {"guard_id": args.guard_id, "guard_type": args.guard_type})
            args.guard_id = str(result["guard"].get("guard_id") or args.guard_id or "")
        if args.run_guard:
            if not args.guard_id:
                guards = store.list_guards(args.hub_id)
                if not guards:
                    raise ValueError("--guard-id is required when no guards exist.")
                args.guard_id = str(guards[0].get("guard_id") or "")
            result["guard_run"] = store.run_guard(args.hub_id, str(args.guard_id))
        if args.run_all_guards:
            result["guard_runs"] = store.run_all_guards(args.hub_id)
        if args.refresh_recurrence:
            result["recurrence"] = store.refresh_recurrence(args.hub_id)
        if args.export:
            result["manifest"] = store.export_knowledge(args.hub_id)
        if args.zip:
            result["zip"] = store.build_zip(args.hub_id)
        if args.verify:
            verification = store.verify_zip(
                args.hub_id,
                {
                    "strict": args.strict,
                    "require_guards_passed": args.require_guards_passed,
                    "require_no_open_recurrence": args.require_no_open_recurrence,
                    "incident_board_package_path": args.incident_board_package,
                    "incident_board_verification_report_path": args.incident_board_verification_report,
                    "hub_verification_report_path": args.hub_verification_report,
                },
            )
            result["verification"] = verification
            result["verification_summary"] = verification.get("summary", {})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if "verification" in result:
                print_trust_operations_incident_knowledge_verification_report(result["verification"])
            else:
                print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "public-trust-center":
        from song_agent.public_trust_center import public_trust_center_summary
        from song_agent.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStore, anchor_registry_summary
        from song_agent.public_trust_center_anchor_registry_verifier import (
            verify_public_trust_center_anchor_registry_package,
            write_public_trust_center_anchor_registry_verification_report,
        )
        from song_agent.public_trust_center_anchor_transparency import PublicTrustCenterAnchorTransparencyStore, anchor_transparency_summary
        from song_agent.public_trust_center_anchor_transparency_verifier import (
            verify_public_trust_center_anchor_transparency_package,
            write_public_trust_center_anchor_transparency_verification_report,
        )
        from song_agent.public_trust_center_acceptance_board import PublicTrustCenterAcceptanceBoardStore
        from song_agent.public_trust_center_distribution_kit_acceptance import PublicTrustCenterDistributionKitAcceptanceStore, accepted_evidence_summary
        from song_agent.public_trust_center_distribution_kit import PublicTrustCenterDistributionKitStore, distribution_kit_summary

        parser = build_public_trust_center_parser()
        args = parser.parse_args(raw_args[1:])
        store = _build_public_trust_center_store()
        anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=store)
        anchor_transparency_store = PublicTrustCenterAnchorTransparencyStore(anchor_registry_store=anchor_store)
        distribution_kit_store = PublicTrustCenterDistributionKitStore(
            trust_center_store=store,
            anchor_registry_store=anchor_store,
            anchor_transparency_store=anchor_transparency_store,
        )
        distribution_kit_acceptance_store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=distribution_kit_store)
        acceptance_board_store = PublicTrustCenterAcceptanceBoardStore(acceptance_store=distribution_kit_acceptance_store)
        payload: dict[str, Any] = {
            "center_id": args.center_id,
            "attestation_profile": args.profile,
            "release_ids": args.release_ids,
            "portfolio_ids": args.portfolio_ids,
            "include_all_releases": not bool(args.release_ids),
            "include_all_portfolios": not bool(args.portfolio_ids),
            "require_registry_current": True,
            "require_portal_current": True,
            "require_transparency_current": True,
            "require_acknowledgement_current": args.require_acknowledgement_current,
            "include_delivery": args.include_delivery,
            "include_distribution": args.include_delivery and args.include_distribution,
            "include_submission": args.include_delivery and args.include_submission,
            "include_submission_evidence": args.include_delivery and args.include_submission_evidence,
            "include_operations": args.include_delivery and args.include_operations,
            "require_release_signoff": args.require_release_signoff,
            "require_distribution_signed": args.require_distribution_signed,
            "require_submission_accepted": args.require_submission_accepted,
            "require_submission_evidence_signed": args.require_submission_evidence_signed,
            "require_operations_signed": args.require_operations_signed,
            "require_operations_audit_verified": args.require_operations_audit_verified,
            "require_operations_reviewer_pack_verified": args.require_operations_reviewer_pack_verified,
        }
        if args.name:
            payload["name"] = args.name
        result: dict[str, Any] = {"ok": True, "center_id": args.center_id}
        if args.refresh:
            report = store.refresh_report(args.center_id, payload)
            result.update({"report": report, "summary": public_trust_center_summary(report), "stale": False})
        else:
            config = store.read_config(args.center_id, default={}) or store.create_or_update_center(payload)
            report = store.read_report(args.center_id, default={})
            summary = public_trust_center_summary(report) if report else {"status": "missing", "center_id": args.center_id}
            if report:
                summary["stale"] = store.report_is_stale(args.center_id, report)
            result.update({"config": config, "report": report, "summary": summary, "stale": summary.get("stale", False)})
        if args.export:
            result["manifest"] = store.export_center(args.center_id)
        if args.zip:
            result["zip"] = store.build_zip(args.center_id)
        if args.verify:
            verify_payload = {
                "strict": args.strict,
                "require_registry_current": args.require_registry_current,
                "require_portal_current": args.require_portal_current,
                "require_transparency_current": args.require_transparency_current,
                "require_acknowledgement_current": args.require_acknowledgement_current,
                "require_release_readiness": args.require_release_readiness,
                "require_delivery_readiness": args.require_delivery_readiness,
                "require_distribution_ready": args.require_distribution_ready,
                "require_submission_accepted": args.require_submission_accepted,
                "require_submission_evidence": args.require_submission_evidence,
                "require_operations_signed": args.require_operations_signed,
                "require_operations_audit": args.require_operations_audit,
                "require_operations_reviewer_pack": args.require_operations_reviewer_pack,
                "require_anchor_registry_current": args.require_anchor_registry_current,
                "require_anchor_published": args.require_anchor_published,
                "require_anchor_not_revoked": args.require_anchor_not_revoked,
                "require_anchor_transparency_current": args.require_anchor_transparency_current,
                "require_anchor_checkpoint": args.require_anchor_checkpoint,
            }
            if args.require_anchor_registry_current or args.require_anchor_published or args.require_anchor_not_revoked:
                verify_payload["anchor_registry_path"] = anchor_store.zip_path(args.center_id)
            if args.require_anchor_transparency_current or args.require_anchor_checkpoint:
                verify_payload["anchor_transparency_path"] = anchor_transparency_store.zip_path(args.center_id)
            if args.require_anchor_checkpoint:
                verify_payload["anchor_checkpoint_path"] = anchor_transparency_store.current_checkpoint_path(args.center_id)
            verification = store.verify_zip(args.center_id, verify_payload)
            result["verification"] = verification
            result["verification_summary"] = verification.get("summary", {})
        if args.archive:
            result["archive"] = store.archive_snapshot(args.center_id)
        if args.anchor_register:
            registered = anchor_store.register_current_anchor(args.center_id, {"reason": args.anchor_reason})
            result["anchor_registry"] = registered
            result["anchor_summary"] = anchor_registry_summary(registered.get("registry") if isinstance(registered.get("registry"), dict) else {})
        if args.anchor_publish:
            registry = anchor_store.read_registry(args.center_id, default={})
            entry_id = str(registry.get("current_entry_id") or "")
            if not entry_id:
                registered = anchor_store.register_current_anchor(args.center_id, {"reason": args.anchor_reason})
                entry_id = str((registered.get("entry") if isinstance(registered.get("entry"), dict) else {}).get("entry_id") or "")
            published = anchor_store.publish_entry(args.center_id, entry_id, {"reason": args.anchor_reason, "supersede_current": True})
            result["anchor_publish"] = published
            result["anchor_summary"] = anchor_registry_summary(published.get("registry") if isinstance(published.get("registry"), dict) else {})
        if args.anchor_revoke:
            revoked = anchor_store.revoke_entry(args.center_id, args.anchor_revoke, {"reason": args.anchor_reason})
            result["anchor_revoke"] = revoked
            result["anchor_summary"] = anchor_registry_summary(revoked.get("registry") if isinstance(revoked.get("registry"), dict) else {})
        if args.anchor_export:
            result["anchor_manifest"] = anchor_store.export_registry(args.center_id)
        if args.anchor_zip:
            result["anchor_zip"] = anchor_store.build_zip(args.center_id)
        if args.anchor_verify:
            anchor_verification = verify_public_trust_center_anchor_registry_package(
                anchor_store.zip_path(args.center_id),
                strict=args.strict,
                require_current=args.require_anchor_registry_current,
                require_anchor_published=args.require_anchor_published,
                require_anchor_not_revoked=args.require_anchor_not_revoked,
            )
            write_public_trust_center_anchor_registry_verification_report(anchor_verification, anchor_store.verification_report_path(args.center_id))
            result["anchor_verification"] = anchor_verification
            result["anchor_verification_summary"] = anchor_verification.get("summary", {})
        if args.anchor_transparency_refresh:
            report = anchor_transparency_store.refresh_report(args.center_id, {"reason": args.anchor_reason})
            result["anchor_transparency"] = report
            result["anchor_transparency_summary"] = anchor_transparency_summary(report)
        if args.anchor_checkpoint_create:
            checkpoint = anchor_transparency_store.create_checkpoint(args.center_id, {"reason": args.anchor_reason})
            result["anchor_checkpoint"] = checkpoint
        if args.anchor_transparency_export:
            result["anchor_transparency_manifest"] = anchor_transparency_store.export_transparency(args.center_id)
        if args.anchor_transparency_zip:
            result["anchor_transparency_zip"] = anchor_transparency_store.build_zip(args.center_id)
        if args.anchor_transparency_verify:
            transparency_verification = verify_public_trust_center_anchor_transparency_package(
                anchor_transparency_store.zip_path(args.center_id),
                strict=args.strict,
                checkpoint_path=anchor_transparency_store.current_checkpoint_path(args.center_id),
                anchor_registry_path=anchor_store.zip_path(args.center_id),
                require_current_checkpoint=args.require_anchor_transparency_current or args.require_anchor_checkpoint,
                require_published_anchor=args.require_anchor_published or args.require_anchor_registry_current,
                require_not_revoked=args.require_anchor_not_revoked,
            )
            write_public_trust_center_anchor_transparency_verification_report(transparency_verification, anchor_transparency_store.verification_report_path(args.center_id))
            result["anchor_transparency_verification"] = transparency_verification
            result["anchor_transparency_verification_summary"] = transparency_verification.get("summary", {})
        if args.distribution_kit_refresh:
            kit_report = distribution_kit_store.refresh_report(args.center_id)
            result["distribution_kit"] = kit_report
            result["distribution_kit_summary"] = distribution_kit_summary(kit_report)
        if args.distribution_kit_export:
            result["distribution_kit_manifest"] = distribution_kit_store.export_kit(args.center_id)
        if args.distribution_kit_zip:
            result["distribution_kit_zip"] = distribution_kit_store.build_zip(args.center_id)
        if args.distribution_kit_verify:
            kit_verification = distribution_kit_store.verify_zip(
                args.center_id,
                {
                    "strict": args.strict,
                    "deep": True,
                    "require_current": True,
                    "require_delivery_readiness": args.require_delivery_readiness,
                    "require_anchor_registry_current": True,
                    "require_anchor_published": True,
                    "require_anchor_not_revoked": True,
                    "require_anchor_transparency_current": True,
                    "require_anchor_checkpoint": True,
                },
            )
            result["distribution_kit_verification"] = kit_verification
            result["distribution_kit_verification_summary"] = kit_verification.get("summary", {})
        if args.distribution_kit_acceptance_template:
            template = distribution_kit_acceptance_store.create_response_template(args.center_id)
            result["distribution_kit_acceptance_template"] = template
        if args.distribution_kit_acceptance_response_file is not None or args.distribution_kit_acceptance_response_base64:
            import_payload: dict[str, Any] = {}
            if args.distribution_kit_acceptance_response_file is not None:
                import_payload["content"] = args.distribution_kit_acceptance_response_file.read_text(encoding="utf-8")
            if args.distribution_kit_acceptance_response_base64:
                import_payload["content_base64"] = args.distribution_kit_acceptance_response_base64
            imported = distribution_kit_acceptance_store.import_response(args.center_id, import_payload)
            result["distribution_kit_acceptance_import"] = imported
            result["distribution_kit_acceptance_summary"] = imported.get("response", {})
        if args.distribution_kit_acceptance_verify_response:
            if not args.distribution_kit_acceptance_response_id:
                raise SystemExit("--distribution-kit-acceptance-response-id is required with --distribution-kit-acceptance-verify-response")
            verification = distribution_kit_acceptance_store.verify_response(args.center_id, args.distribution_kit_acceptance_response_id)
            result["distribution_kit_acceptance_response_verification"] = verification
        if args.distribution_kit_accepted_evidence_export:
            manifest = distribution_kit_acceptance_store.export_accepted_evidence(args.center_id, args.distribution_kit_acceptance_response_id)
            result["distribution_kit_accepted_evidence_manifest"] = manifest
        if args.distribution_kit_accepted_evidence_zip:
            zip_info = distribution_kit_acceptance_store.build_accepted_evidence_zip(args.center_id, args.distribution_kit_acceptance_response_id)
            result["distribution_kit_accepted_evidence_zip"] = zip_info
            evidence = distribution_kit_acceptance_store.read_evidence(args.center_id, zip_info.get("evidence_id"), default={})
            result["distribution_kit_accepted_evidence_summary"] = accepted_evidence_summary(evidence)
        if args.distribution_kit_accepted_evidence_verify:
            evidence_id = None
            if args.distribution_kit_acceptance_response_id:
                evidence = distribution_kit_acceptance_store.refresh_accepted_evidence(args.center_id, {"response_id": args.distribution_kit_acceptance_response_id})
                evidence_id = str(evidence.get("evidence_id") or "")
            verification = distribution_kit_acceptance_store.verify_accepted_evidence_zip(args.center_id, evidence_id, {"strict": args.strict, "require_current": True})
            result["distribution_kit_accepted_evidence_verification"] = verification
            result["distribution_kit_accepted_evidence_verification_summary"] = verification.get("summary", {})
        if args.distribution_kit_acceptance_change_request:
            if not args.distribution_kit_acceptance_response_id:
                raise SystemExit("--distribution-kit-acceptance-response-id is required with --distribution-kit-acceptance-change-request")
            result["distribution_kit_acceptance_change_request"] = distribution_kit_acceptance_store.create_change_request_draft(args.center_id, args.distribution_kit_acceptance_response_id, {"source": "cli"})
        if args.acceptance_board_policy_save is not None:
            result["acceptance_board_policy"] = acceptance_board_store.save_policy(args.center_id, read_json(args.acceptance_board_policy_save))
        if args.acceptance_board_refresh:
            board = acceptance_board_store.refresh_report(args.center_id)
            result["acceptance_board"] = board
            result["acceptance_board_summary"] = acceptance_board_store.summary(args.center_id)
        if args.acceptance_board_export:
            result["acceptance_board_manifest"] = acceptance_board_store.export_board(args.center_id)
        if args.acceptance_board_zip:
            result["acceptance_board_zip"] = acceptance_board_store.build_zip(args.center_id)
        if args.acceptance_board_verify:
            board_verification = acceptance_board_store.verify_zip(
                args.center_id,
                {
                    "strict": args.strict,
                    "require_ready": args.require_ready,
                    "require_quorum": args.require_quorum,
                    "require_no_conflicts": args.require_no_conflicts,
                    "min_accepted_count": args.min_accepted_count,
                    "min_accepted_organizations": args.min_accepted_organizations,
                    "required_roles": args.required_roles,
                    "use_distribution_kit": True,
                },
            )
            result["acceptance_board_verification"] = board_verification
            result["acceptance_board_verification_summary"] = board_verification.get("summary", {})
        if args.acceptance_board_signoff_draft:
            result["acceptance_board_signoff_draft"] = acceptance_board_store.create_signoff_draft(args.center_id, {"source": "cli"})
        if args.acceptance_board_signoff:
            signoff = acceptance_board_store.signoff(args.center_id, {"signed_by": args.acceptance_board_signed_by, "reason": args.acceptance_board_signoff_reason})
            result["acceptance_board_signoff"] = signoff
            result["acceptance_board_summary"] = acceptance_board_store.summary(args.center_id)
        if args.acceptance_board_change_request_create:
            change = acceptance_board_store.create_change_request(args.center_id, {"reason": args.acceptance_board_signoff_reason, "requested_by": args.acceptance_board_signed_by})
            result["acceptance_board_change_request"] = change
        if args.acceptance_board_change_request_approve:
            if not args.acceptance_board_change_request_id:
                raise SystemExit("--acceptance-board-change-request-id is required with --acceptance-board-change-request-approve")
            change = acceptance_board_store.approve_change_request(args.center_id, args.acceptance_board_change_request_id, {"approved_by": args.acceptance_board_signed_by, "reason": args.acceptance_board_signoff_reason})
            result["acceptance_board_change_request"] = change
        if args.acceptance_board_reset_signoff:
            if not args.acceptance_board_change_request_id:
                raise SystemExit("--acceptance-board-change-request-id is required with --acceptance-board-reset-signoff")
            reset = acceptance_board_store.reset_signoff(args.center_id, {"change_request_id": args.acceptance_board_change_request_id, "reason": args.acceptance_board_signoff_reason})
            result["acceptance_board_signoff_reset"] = reset
            result["acceptance_board_summary"] = acceptance_board_store.summary(args.center_id)
        if args.acceptance_board_signoff_archive_export:
            result["acceptance_board_signoff_archive_manifest"] = acceptance_board_store.export_signoff_archive(args.center_id)
        if args.acceptance_board_signoff_archive_zip:
            result["acceptance_board_signoff_archive_zip"] = acceptance_board_store.build_signoff_archive_zip(args.center_id)
        if args.acceptance_board_signoff_archive_verify:
            archive_verification = acceptance_board_store.verify_signoff_archive_zip(
                args.center_id,
                {
                    "strict": args.strict,
                    "require_signed": True,
                    "require_current": True,
                    "require_ready": True,
                    "use_board_zip": True,
                    "use_board_verification": True,
                    "use_distribution_kit": True,
                    "use_accepted_evidence": True,
                },
            )
            result["acceptance_board_signoff_archive_verification"] = archive_verification
            result["acceptance_board_signoff_archive_verification_summary"] = archive_verification.get("summary", {})
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_public_trust_center_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "verify-human-review-pack":
        from song_agent.human_review_verifier import (
            human_review_verification_exit_code,
            print_human_review_verification_report,
            verify_human_review_pack,
            write_human_review_verification_report,
        )

        parser = build_verify_human_review_pack_parser()
        args = parser.parse_args(raw_args[1:])
        report = verify_human_review_pack(
            args.zip_path,
            strict=args.strict,
            max_zip_size_mb=args.max_zip_size_mb,
            max_uncompressed_size_mb=args.max_uncompressed_size_mb,
            max_entry_count=args.max_entry_count,
        )
        if args.report_out is not None:
            write_human_review_verification_report(report, args.report_out)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_human_review_verification_report(report)
        raise SystemExit(human_review_verification_exit_code(report))
    elif raw_args and raw_args[0] == "acceptance-check":
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
            write_json(args.report_out, report)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_acceptance_check_report(report)
        raise SystemExit(0 if report.get("status") in {"passed", "needs_review"} else 1)
    elif raw_args and raw_args[0] == "audio-health":
        from song_agent.audio_health import analyze_wav_health

        parser = build_audio_health_parser()
        args = parser.parse_args(raw_args[1:])
        report = analyze_wav_health(
            args.wav_path,
            expected_sample_rate=args.expected_sample_rate,
            expected_channels=args.expected_channels,
            expected_bit_depth=args.expected_bit_depth,
        )
        if args.report_out is not None:
            write_json(args.report_out, report)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"MusicForge audio-health\nstatus: {report.get('status')}\nwav_sha256: {report.get('wav_sha256')}")
        raise SystemExit(0 if report.get("status") in {"passed", "warning"} else 1)
    elif raw_args and raw_args[0] == "audio-profile":
        from song_agent.audio_profiles import AudioProfileStore

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
    elif raw_args and raw_args[0] == "release-audio-review":
        from song_agent.audio_review_evidence import AudioReviewEvidenceStore, audio_review_summary_public
        from song_agent.projects import ProjectStore
        from song_agent.releases import ReleaseStore

        parser = build_release_audio_review_parser()
        args = parser.parse_args(raw_args[1:])
        project_store = ProjectStore()
        release_store = ReleaseStore(project_store=project_store)
        store = AudioReviewEvidenceStore(release_store, project_store)
        if args.action == "list":
            reviews = store.list_reviews(args.release_id)
            summary = store.build_summary(args.release_id)
            result = {"ok": True, "release_id": args.release_id, "reviews": reviews, "summary": audio_review_summary_public(summary)}
        elif args.action == "summary":
            summary = store.write_summary(args.release_id) if args.write else store.build_summary(args.release_id)
            result = {"ok": True, "release_id": args.release_id, "summary": audio_review_summary_public(summary), "audio_review_summary": summary}
        elif args.action == "add":
            review = store.create_review(
                args.release_id,
                {
                    "track_id": args.track_id,
                    "status": args.status,
                    "review_mode": args.review_mode,
                    "rating": args.rating,
                    "reviewer": {"name": args.reviewer},
                    "notes": args.notes,
                    "playback_confirmed": args.playback_confirmed,
                },
            )
            summary = store.build_summary(args.release_id)
            result = {"ok": True, "release_id": args.release_id, "review": review, "summary": audio_review_summary_public(summary)}
        elif args.action == "create-task":
            payload = {key: value for key, value in {"title": args.title, "instruction": args.instruction}.items() if value}
            result = {"ok": True, "release_id": args.release_id, **store.create_review_task_from_marker(args.release_id, args.review_id, args.marker_id, payload)}
        else:
            parser.error("unknown release-audio-review action")
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_release_audio_review_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "release-encode":
        from song_agent.audio_encoding import AudioEncodingStore
        from song_agent.audio_encoding_profiles import AudioEncodingProfileStore
        from song_agent.projects import ProjectStore
        from song_agent.releases import ReleaseStore

        parser = build_release_encode_parser()
        args = parser.parse_args(raw_args[1:])
        project_store = ProjectStore()
        release_store = ReleaseStore(project_store=project_store)
        profile_store = AudioEncodingProfileStore(release_store.root.parent / "audio-encoding-profiles")
        store = AudioEncodingStore(release_store, project_store=project_store, profile_store=profile_store)
        result = store.render(args.release_id, {"profile_ids": [item.strip() for item in str(args.profiles or "").split(",") if item.strip()], "force": args.force})
        payload = {"ok": True, **result}
        if args.report_out is not None:
            write_json(args.report_out, payload)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            summary = payload.get("summary", {})
            print(f"MusicForge release-encode\nrelease: {args.release_id}\nstatus: {summary.get('status')}\nprofiles: {summary.get('profile_count', 0)}")
        raise SystemExit(0 if payload.get("summary", {}).get("status") in {"completed", "warning"} else 1)
    elif raw_args and raw_args[0] == "encoded-audio-acceptance":
        from song_agent.audio_encoding import AudioEncodingStore, normalize_required_profiles
        from song_agent.audio_encoding_profiles import AudioEncodingProfileStore
        from song_agent.encoded_audio_acceptance import EncodedAudioAcceptanceStore, encoded_audio_acceptance_summary_public
        from song_agent.projects import ProjectStore
        from song_agent.releases import ReleaseStore

        parser = build_encoded_audio_acceptance_parser()
        args = parser.parse_args(raw_args[1:])
        project_store = ProjectStore()
        release_store = ReleaseStore(project_store=project_store)
        profile_store = AudioEncodingProfileStore(release_store.root.parent / "audio-encoding-profiles")
        encoding_store = AudioEncodingStore(release_store, project_store=project_store, profile_store=profile_store)
        store = EncodedAudioAcceptanceStore(release_store, project_store=project_store, audio_encoding_store=encoding_store)
        profiles = normalize_required_profiles(args.profiles)
        health = store.refresh_health(args.release_id, profiles) if args.refresh_health else {"profiles": store.list_health(args.release_id)}
        summary = store.write_summary(args.release_id, required_profiles=profiles) if args.write else store.build_summary(args.release_id, required_profiles=profiles)
        payload = {"ok": True, "release_id": args.release_id, "health": health, "summary": encoded_audio_acceptance_summary_public(summary), "encoded_audio_acceptance": summary}
        if args.report_out is not None:
            write_json(args.report_out, payload)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"MusicForge encoded-audio-acceptance\nrelease: {args.release_id}\nstatus: {summary.get('status')}\nprofiles: {summary.get('profile_count', 0)}")
        raise SystemExit(0 if summary.get("status") == "passed" else 1)
    elif raw_args and raw_args[0] == "format-decision":
        from song_agent.audio_encoding import AudioEncodingStore, normalize_required_profiles
        from song_agent.audio_encoding_profiles import AudioEncodingProfileStore
        from song_agent.distribution import DistributionStore
        from song_agent.format_decisions import FormatDecisionStore
        from song_agent.projects import ProjectStore
        from song_agent.releases import ReleaseStore

        parser = build_format_decision_parser()
        args = parser.parse_args(raw_args[1:])
        project_store = ProjectStore()
        release_store = ReleaseStore(project_store=project_store)
        profile_store = AudioEncodingProfileStore(release_store.root.parent / "audio-encoding-profiles")
        encoding_store = AudioEncodingStore(release_store, project_store=project_store, profile_store=profile_store)
        distribution_store = DistributionStore(release_store)
        store = FormatDecisionStore(release_store, project_store=project_store, encoding_store=encoding_store, distribution_store=distribution_store)
        session = store.create_session(args.release_id, {"profiles": normalize_required_profiles(args.profiles)})
        matrix = store.build_matrix(args.release_id, session["session_id"])
        recommendation = store.build_recommendation(args.release_id, session["session_id"])
        selected = normalize_required_profiles(args.select) or recommendation.get("selected_defaults", [])
        archive = normalize_required_profiles(args.archive) or recommendation.get("archive_defaults", [])
        fallback = normalize_required_profiles(args.fallback)
        rejected = normalize_required_profiles(args.reject) or recommendation.get("rejected_defaults", [])
        session = store.select_profiles(
            args.release_id,
            session["session_id"],
            {
                "selected_profiles": selected,
                "archive_profiles": archive,
                "fallback_profiles": fallback,
                "rejected_profiles": rejected,
                "decided_by": args.decided_by,
                "reason": args.reason,
            },
        )
        report = store.build_report(args.release_id, session["session_id"])
        active = store.activate_session(args.release_id, session["session_id"]) if args.activate else {}
        payload = {"ok": True, "release_id": args.release_id, "session": session, "matrix": matrix, "recommendation": recommendation, "report": report, "active_session": active}
        if args.report_out is not None:
            write_json(args.report_out, payload)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"MusicForge format-decision\nrelease: {args.release_id}\nstatus: {report.get('status')}\nselected: {', '.join(report.get('decision', {}).get('selected_profiles', []))}")
        raise SystemExit(0 if report.get("status") in {"passed", "warning"} else 1)
    elif raw_args and raw_args[0] == "acceptance-diff":
        from song_agent.acceptance_diff import build_acceptance_diff

        parser = build_acceptance_diff_parser()
        args = parser.parse_args(raw_args[1:])
        report = build_acceptance_diff(read_json(args.left_report), read_json(args.right_report))
        if args.report_out is not None:
            write_json(args.report_out, report)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_acceptance_diff_report(report)
        raise SystemExit(0 if report.get("status") == "passed" else 1)
    elif raw_args and raw_args[0] == "acceptance-analytics":
        from song_agent.acceptance_analytics import AcceptanceAnalyticsStore, AnalyticsScope, acceptance_analytics_summary

        parser = build_acceptance_analytics_parser()
        args = parser.parse_args(raw_args[1:])
        scope = AnalyticsScope.from_values(scope_type=args.scope, suite_id=args.suite_id, release_id=args.release_id, project_id=args.project_id)
        store = AcceptanceAnalyticsStore()
        report = store.refresh(scope) if args.refresh else store.latest_report(scope)
        if args.report_out is not None:
            write_json(args.report_out, report)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_acceptance_analytics_report(report)
        summary = acceptance_analytics_summary(report)
        raise SystemExit(1 if _acceptance_analytics_fail_on(str(summary.get("readiness_status") or ""), args.fail_on) else 0)
    elif raw_args and raw_args[0] == "acceptance-fix-sprint":
        from song_agent.acceptance_fix_sprints import AcceptanceFixSprintStore, fix_sprint_summary

        parser = build_acceptance_fix_sprint_parser()
        args = parser.parse_args(raw_args[1:])
        store = AcceptanceFixSprintStore()
        if args.action == "create":
            sprint = store.create_from_analytics(
                {
                    "analytics_report_id": args.analytics_report_id,
                    "name": args.name,
                    "max_items": args.max_items,
                    "recommendation_ids": args.recommendation_ids,
                }
            )
            items = store.read_items(sprint.fix_sprint_id)
            result = {"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": fix_sprint_summary(sprint, items)}
        elif args.action == "show":
            sprint = store.read_sprint(args.fix_sprint_id)
            items = store.read_items(args.fix_sprint_id)
            result = {"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": fix_sprint_summary(sprint, items)}
        elif args.action == "list":
            sprints = store.list_sprints(include_archived=args.include_archived)
            result = {"ok": True, "fix_sprints": [sprint.to_dict() for sprint in sprints], "summary": {"fix_sprint_count": len(sprints)}}
        elif args.action == "create-review-tasks":
            result = {"ok": True, **store.create_review_tasks(args.fix_sprint_id, item_id=args.item_id)}
        elif args.action == "create-recheck-suite":
            result = {"ok": True, **store.create_recheck_suite(args.fix_sprint_id, {"profile_id": args.profile} if args.profile else {})}
        elif args.action == "delta":
            report = store.refresh_delta(args.fix_sprint_id) if args.refresh else store.read_delta(args.fix_sprint_id)
            result = {"ok": True, "delta_report": report, "summary": report.get("summary", {})}
        elif args.action == "close":
            report = store.close(args.fix_sprint_id, {"force": args.force, "override_reason": args.override_reason})
            result = {"ok": True, "closeout_report": report, "summary": report.get("summary", {})}
        else:
            parser.error("unknown acceptance-fix-sprint action")
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_acceptance_fix_sprint_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "acceptance-fix-plan":
        from song_agent.acceptance_fix_planning import AcceptanceFixPlanningStore, fix_plan_summary
        from song_agent.acceptance_fix_plan_reviews import AcceptanceFixPlanReviewStore, fix_plan_review_summary

        parser = build_acceptance_fix_plan_parser()
        args = parser.parse_args(raw_args[1:])
        store = AcceptanceFixPlanningStore()
        if args.action == "create":
            plan = store.create({"analytics_report_id": args.analytics_report_id, "kb_report_id": args.kb_report_id, "max_items": args.max_items, "include_hidden_kb": args.include_hidden_kb})
            result = {"ok": True, "fix_plan": plan.to_dict(), "summary": fix_plan_summary(plan)}
        elif args.action == "list":
            plans = store.list_plans(include_archived=args.include_archived)
            result = {"ok": True, "fix_plans": [plan.to_dict() for plan in plans], "summary": {"plan_count": len(plans)}}
        elif args.action == "show":
            plan = store.read_plan(args.plan_id)
            result = {"ok": True, "fix_plan": plan.to_dict(), "summary": fix_plan_summary(plan)}
        elif args.action == "refresh":
            plan = store.refresh_plan(args.plan_id)
            result = {"ok": True, "fix_plan": plan.to_dict(), "summary": fix_plan_summary(plan)}
        elif args.action == "create-fix-sprint":
            result = {"ok": True, **store.create_fix_sprint(args.plan_id, {"name": args.name, "planned_item_ids": args.planned_item_ids, "profile_id": args.profile})}
        elif args.action == "review":
            review_store = AcceptanceFixPlanReviewStore(plan_store=store, fix_sprint_store=store.fix_sprint_store, kb_store=store.kb_store, project_store=store.project_store)
            if args.refresh:
                review = review_store.refresh_for_plan(args.plan_id)
                result = {"ok": True, "outcome_review": review.to_dict(), "summary": fix_plan_review_summary(review)}
            else:
                review = review_store.get_or_missing_for_plan(args.plan_id)
                result = {"ok": True, "outcome_review": review, "summary": fix_plan_review_summary(review)}
        elif args.action == "recommend":
            preview = store.preview({"analytics_report_id": args.analytics_report_id, "kb_report_id": args.kb_report_id, "max_items": args.max_items, "include_hidden_kb": args.include_hidden_kb})
            result = {"ok": True, "fix_plan_preview": preview, "summary": fix_plan_summary(preview)}
        else:
            parser.error("unknown acceptance-fix-plan action")
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_acceptance_fix_plan_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "planning-ruleset":
        from song_agent.planning_rule_simulation import PlanningRuleSimulationStore, ruleset_summary

        parser = build_planning_ruleset_parser()
        args = parser.parse_args(raw_args[1:])
        store = PlanningRuleSimulationStore()
        if args.action == "create":
            payload = {"template": args.template, "name": args.name, "description": args.description}
            ruleset = store.create_ruleset(payload)
            result = {"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}
        elif args.action == "list":
            rulesets = store.list_rulesets(include_archived=args.include_archived)
            result = {"ok": True, "rulesets": [ruleset.to_dict() for ruleset in rulesets], "summary": {"ruleset_count": len(rulesets)}}
        elif args.action == "show":
            ruleset = store.read_ruleset(args.ruleset_id)
            result = {"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}
        elif args.action == "clone":
            ruleset = store.clone_ruleset(args.ruleset_id, {"name": args.name} if args.name else {})
            result = {"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}
        elif args.action == "archive":
            ruleset = store.archive_ruleset(args.ruleset_id)
            result = {"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}
        elif args.action == "validate":
            result = {"ok": True, "validation": store.validate_ruleset(args.ruleset_id)}
        else:
            parser.error("unknown planning-ruleset action")
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_planning_ruleset_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "planning-simulation":
        from song_agent.planning_rule_simulation import PlanningRuleSimulationStore, planning_simulation_summary

        parser = build_planning_simulation_parser()
        args = parser.parse_args(raw_args[1:])
        store = PlanningRuleSimulationStore()
        if args.action == "run":
            scope = {"type": "release" if args.release_id else "project" if args.project_id else "global", "release_id": args.release_id, "project_id": args.project_id}
            simulation = store.create_simulation({"ruleset_id": args.ruleset_id, "scope": scope, "review_ids": args.review_ids, "include_warning_reviews": args.include_warning_reviews, "exclude_synthetic_only": args.exclude_synthetic_only})
            result = {"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)}
        elif args.action == "show":
            simulation = store.read_simulation(args.simulation_id)
            result = {"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)}
        elif args.action == "refresh":
            simulation = store.refresh_simulation(args.simulation_id)
            result = {"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)}
        elif args.action == "archive":
            simulation = store.archive_simulation(args.simulation_id)
            result = {"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)}
        elif args.action == "list":
            simulations = store.list_simulations(include_archived=args.include_archived)
            result = {"ok": True, "simulations": [simulation.to_dict() for simulation in simulations], "summary": {"simulation_count": len(simulations)}}
        else:
            parser.error("unknown planning-simulation action")
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_planning_simulation_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "planning-rule-governance":
        from song_agent.planning_rule_governance import PlanningRuleGovernanceStore, governance_summary, promotion_summary

        parser = build_planning_rule_governance_parser()
        args = parser.parse_args(raw_args[1:])
        store = PlanningRuleGovernanceStore()
        if args.action == "active":
            version = store.active_version()
            result = {"ok": True, "active": store.active_pointer(), "version": version.to_dict() if version else {}, "summary": store.active_summary()}
        elif args.action == "versions":
            versions = store.list_versions(include_archived=args.include_archived)
            result = {"ok": True, "versions": [version.to_dict() for version in versions], "summary": {"version_count": len(versions), "active": store.active_summary()}}
        elif args.action == "version":
            version = store.read_version(args.version_id)
            result = {"ok": True, "version": version.to_dict(), "frozen_ruleset_summary": {}, "summary": governance_summary(version, active=store.active_pointer(), evidence_stale=store.version_evidence_is_stale(version))}
        elif args.action == "promotions":
            promotions = store.list_promotions(include_archived=args.include_archived)
            result = {"ok": True, "promotions": [promotion.to_dict() for promotion in promotions], "summary": {"promotion_count": len(promotions)}}
        elif args.action == "promotion":
            promotion = store.read_promotion(args.promotion_id)
            result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
        elif args.action == "promote-request":
            promotion = store.create_promotion({"ruleset_id": args.ruleset_id, "simulation_id": args.simulation_id, "note": args.note})
            result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
        elif args.action == "approve":
            promotion = store.approve_promotion(args.promotion_id, {"approved_by": args.approved_by, "approval_note": args.note, "force": args.force, "override_reason": args.override_reason})
            result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
        elif args.action == "reject":
            promotion = store.reject_promotion(args.promotion_id, {"rejected_by": args.rejected_by, "reason": args.reason})
            result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
        elif args.action == "promote":
            promoted = store.promote(args.promotion_id, {"promoted_by": args.promoted_by, "activation_note": args.activation_note})
            result = {"ok": True, "version": promoted["version"].to_dict(), "active": promoted["active"], "promotion": promoted["promotion"].to_dict(), "summary": promoted["summary"]}
        elif args.action == "rollback":
            rolled_back = store.rollback({"target_version_id": args.target_version_id, "rolled_back_by": args.rolled_back_by, "reason": args.reason})
            result = {"ok": True, "version": rolled_back["version"].to_dict(), "active": rolled_back["active"], "summary": rolled_back["summary"]}
        elif args.action == "events":
            events = store.events(limit=args.limit)
            result = {"ok": True, "events": events, "summary": {"event_count": len(events)}}
        else:
            parser.error("unknown planning-rule-governance action")
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_planning_rule_governance_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "planning-rule-impact":
        from song_agent.planning_rule_impact import PlanningRuleImpactStore, planning_rule_impact_summary

        parser = build_planning_rule_impact_parser()
        args = parser.parse_args(raw_args[1:])
        store = PlanningRuleImpactStore()
        if args.action == "refresh":
            scope = {"type": "release" if args.release_id else "project" if args.project_id else "global", "release_id": args.release_id, "project_id": args.project_id}
            report = store.refresh({"scope": scope, "include_legacy": not args.exclude_legacy, "include_superseded": not args.exclude_superseded})
            result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)}
        elif args.action == "list":
            reports = store.list_reports(include_archived=args.include_archived, release_id=args.release_id, project_id=args.project_id)
            result = {"ok": True, "reports": [report.to_dict() for report in reports], "summary": {"report_count": len(reports), "latest": planning_rule_impact_summary(reports[0]) if reports else {"status": "missing"}}}
        elif args.action == "show":
            report = store.get_report(args.report_id)
            result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report), "stale": store.report_is_stale(report), "integrity_ok": store.report_integrity_ok(report)}
        elif args.action == "refresh-existing":
            report = store.refresh_report(args.report_id)
            result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)}
        elif args.action == "archive":
            report = store.archive_report(args.report_id)
            result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)}
        else:
            parser.error("unknown planning-rule-impact action")
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_planning_rule_impact_result(result)
        raise SystemExit(0)
    elif raw_args and raw_args[0] == "acceptance-kb":
        from song_agent.acceptance_kb import AcceptanceKnowledgeBaseStore, knowledge_entry_summary, knowledge_report_summary

        parser = build_acceptance_kb_parser()
        args = parser.parse_args(raw_args[1:])
        store = AcceptanceKnowledgeBaseStore()
        if args.action == "refresh":
            scope = {"type": "global", "project_id": args.project_id, "release_id": args.release_id}
            report = store.refresh(scope)
            result = {"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)}
        elif args.action == "report":
            report = store.latest_report()
            result = {"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)}
        elif args.action == "entries":
            entries = store.list_entries(include_hidden=args.include_hidden)
            result = {"ok": True, "entries": [knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}}
        elif args.action == "show":
            entry = store.read_entry(args.entry_id)
            result = {"ok": True, "entry": entry.to_dict(), "summary": knowledge_entry_summary(entry)}
        elif args.action == "search":
            query = {"issue_type": args.issue_type, "style": args.style, "song_id": args.song_id, "project_id": args.project_id, "release_id": args.release_id, "outcome_status": args.outcome_status}
            entries = store.search_entries(query)
            result = {"ok": True, "entries": [knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}}
        elif args.action == "recommend":
            recommendation = store.recommend({"issue_types": args.issue_types, "style": args.style, "song_id": args.song_id, "project_id": args.project_id, "release_id": args.release_id})
            result = {"ok": True, "recommendation": recommendation}
        else:
            parser.error("unknown acceptance-kb action")
        if args.report_out is not None:
            write_json(args.report_out, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_acceptance_kb_result(result)
        raise SystemExit(0)
    else:
        parser = build_parser()
        args = parser.parse_args(raw_args)

    request_path = args.request
    if request_path is None:
        parser.error("the following arguments are required: request")

    generate_from_file(
        request_path,
        out_dir=args.out,
        dry_run=args.dry_run,
        resume=args.resume,
        force=args.force,
        pipeline_mode=args.pipeline_mode,
    )


def generate_from_file(
    request_path: Path,
    *,
    out_dir: Path | None = None,
    dry_run: bool = False,
    resume: bool = False,
    force: bool = False,
    pipeline_mode: str = "single",
) -> tuple[Path, Path] | None:
    raw = json.loads(request_path.read_text(encoding="utf-8"))
    request = SongRequest.from_dict(raw)

    if dry_run:
        print(json.dumps(request.to_dict(), ensure_ascii=False, indent=2))
        return None

    plan_path, midi_path = generate_request(
        request,
        out_dir=out_dir,
        resume=resume,
        force=force,
        pipeline_mode=pipeline_mode,
    )
    print(f"Wrote song plan: {plan_path}")
    print(f"Wrote MIDI: {midi_path}")
    return plan_path, midi_path


def run_doctor(*, provider_test: bool = False) -> None:
    print("MusicForge doctor")
    print(f"python: ok ({sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro})")
    print(f"cwd writable: {_writable_status(Path.cwd())}")
    print(f"runs writable: {_writable_status(Path('runs'))}")
    try:
        config, _sources = load_provider_config()
        if provider_configured(config):
            print(
                "provider config: configured "
                f"({config.wire_api}, model={config.model}, key={config.to_public_dict()['api_key_masked'] or '-'})"
            )
        elif config.model or config.base_url or config.api_key:
            print("provider config: warning incomplete")
        else:
            print("provider config: missing")
        if provider_test:
            result = test_provider_config(config)
            print(f"provider test: ok ({result['provider']['wire_api']})")
    except ProviderError as exc:
        print(f"provider config: warning {exc}")
        if provider_test:
            print(f"provider test: failed ({exc})")
    print("local deterministic mode: ok")


def print_ga_readiness_report(report: dict[str, Any]) -> None:
    print("MusicForge GA readiness")
    print(f"status: {report.get('status')}")
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    for key in (
        "doctor_status",
        "release_check_latest_status",
        "release_check_ga_status",
        "acceptance_status",
        "renderer_status",
        "provider_status",
        "trust_final_readiness_status",
        "git_status",
    ):
        print(f"{key}: {summary.get(key, 'unknown')}")
    for check in report.get("checks") or []:
        if not isinstance(check, dict):
            continue
        print(f"{check.get('check_id')}: {check.get('status')} ({check.get('severity')})")
        if check.get("message"):
            print(f"  {check.get('message')}")
    actions = [item for item in report.get("next_actions") or [] if isinstance(item, dict)]
    if actions:
        print("next actions:")
        for item in actions[:10]:
            print(f"- {item.get('check_id')}: {item.get('action')}")


def run_acceptance_check(
    *,
    out_dir: Path,
    profile_id: str,
    cases: int,
    render_audio_mode: str,
    auto_review: bool,
    min_rating: int,
    manual_required: bool = False,
) -> dict[str, Any]:
    from song_agent.acceptance_profiles import get_acceptance_profile
    from song_agent.music_acceptance import AcceptanceStore, build_acceptance_report, default_acceptance_song_cases
    from song_agent.music_health import music_health_allows_review

    profile = get_acceptance_profile(profile_id)
    if cases == 6 and profile.case_count != 6:
        cases = profile.case_count
    if render_audio_mode == "require":
        render_audio_mode = "always"
    render_audio_mode = render_audio_mode if render_audio_mode != "auto" or profile.render_audio == "auto" else profile.render_audio
    store = AcceptanceStore(out_dir)
    suite_payload = {
        "name": f"v4.5 {profile.profile_id} music acceptance",
        "mode": profile.profile_id,
        "profile_id": profile.profile_id,
        "min_rating": max(min_rating, profile.min_rating),
        "require_audio_if_renderer_configured": profile.require_audio_if_renderer_configured,
        "allow_synthetic_review": profile.allow_synthetic_review and not manual_required,
        "require_manual_review": profile.require_manual_review or manual_required,
        "release_ready_profile": profile.release_ready,
    }
    if render_audio_mode == "never":
        suite_payload["require_audio_if_renderer_configured"] = False
    suite = store.create_suite(suite_payload)
    for index, song in enumerate(default_acceptance_song_cases(cases), start=1):
        request = song["request"]
        case = store.add_case(
            suite.suite_id,
            {
                "name": song.get("title") or request.get("style"),
                "source_type": "regression_songbook",
                "song_id": song.get("song_id"),
                "songbook_id": song.get("songbook_id") or "builtin_v1",
                "songbook_version": song.get("songbook_version") or "2026-05-19",
                "expectations": song.get("expectations") or {},
                "request": request,
            },
        )
        store.generate_case(suite.suite_id, case.case_id, render_audio_mode=render_audio_mode)
        health = store.run_health(suite.suite_id, case.case_id)
        if auto_review and profile.allow_synthetic_review and music_health_allows_review(health):
            store.write_review(
                suite.suite_id,
                case.case_id,
                {
                    "rating": max(min_rating, 4),
                    "status": "accepted",
                    "playback_confirmed": True,
                    "listened_by": "acceptance-check",
                    "audio_mode": "midi",
                    "review_mode": "synthetic",
                    "notes": f"Synthetic acceptance smoke review for case {index}; MIDI artifact was generated and health checks were reviewed.",
                },
            )
    report = store.build_report(suite.suite_id) if auto_review else build_acceptance_report(store, store.get_suite(suite.suite_id))
    if not auto_review:
        report = {**report, "status": "needs_review", "summary": {**report.get("summary", {}), "review_required": True}}
        write_json(store.report_path(suite.suite_id), report)
    elif report.get("status") == "passed":
        store.signoff(suite.suite_id, {"signed_by": "acceptance-check", "notes": "Synthetic CI acceptance signoff."})
        report = store.read_report(suite.suite_id)
    return report


def print_acceptance_check_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge acceptance-check")
    print(f"status: {report.get('status')}")
    print(f"suite: {report.get('suite_id')}")
    print(f"cases: {summary.get('case_count', 0)}")
    print(f"accepted: {summary.get('accepted_count', 0)}")
    print(f"average_rating: {summary.get('average_rating')}")
    print(f"renderer: {summary.get('renderer_status')}")
    print(f"acceptance_status: {summary.get('acceptance_status')}")


def print_acceptance_diff_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge acceptance-diff")
    print(f"status: {report.get('status')}")
    print(f"left: {report.get('left_suite_id')}")
    print(f"right: {report.get('right_suite_id')}")
    print(f"songs: {summary.get('song_count', 0)}")
    print(f"new_blockers: {summary.get('new_blocker_count', 0)}")
    print(f"rating_regressions: {summary.get('rating_regression_count', 0)}")


def print_release_audio_review_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    review = result.get("review") if isinstance(result.get("review"), dict) else {}
    print("MusicForge release-audio-review")
    print(f"release: {result.get('release_id') or summary.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or review.get('status') or result.get('status') or '-'}")
    print(f"tracks: {summary.get('track_count', 0)}")
    print(f"manual accepted: {summary.get('manual_accepted_track_count', 0)}")
    print(f"missing: {len(summary.get('missing_track_ids', []) or [])}")
    print(f"stale: {summary.get('stale_review_count', 0)}")
    print(f"needs_fix: {summary.get('needs_fix_track_count', 0)}")
    if review:
        print(f"review: {review.get('review_id')}")
    if result.get("task_id"):
        print(f"task: {result.get('task_id')}")
    if result.get("reviews") is not None:
        print(f"reviews: {len(result.get('reviews') or [])}")


def print_acceptance_analytics_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    source = report.get("source_summary") if isinstance(report.get("source_summary"), dict) else {}
    print("MusicForge acceptance-analytics")
    print(f"readiness: {summary.get('readiness_status')}")
    print(f"scope: {(report.get('scope') or {}).get('type') if isinstance(report.get('scope'), dict) else 'global'}")
    print(f"report: {report.get('report_id')}")
    print(f"suites: {source.get('suite_count', 0)}")
    print(f"cases: {summary.get('case_count', 0)}")
    print(f"manual_coverage: {summary.get('manual_coverage_rate', 0.0)}")
    print(f"average_rating: {summary.get('average_rating')}")
    print(f"issues: {summary.get('issue_count', 0)}")
    print(f"recommendations: {summary.get('recommendation_count', 0)}")


def print_acceptance_fix_sprint_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    sprint = result.get("fix_sprint") if isinstance(result.get("fix_sprint"), dict) else {}
    delta = result.get("delta_report") if isinstance(result.get("delta_report"), dict) else {}
    closeout = result.get("closeout_report") if isinstance(result.get("closeout_report"), dict) else {}
    print("MusicForge acceptance-fix-sprint")
    print(f"fix_sprint: {summary.get('fix_sprint_id') or sprint.get('fix_sprint_id') or delta.get('fix_sprint_id') or closeout.get('fix_sprint_id') or '-'}")
    print(f"status: {summary.get('status') or sprint.get('status') or closeout.get('status') or '-'}")
    if "item_count" in summary:
        print(f"items: {summary.get('item_count', 0)}")
        print(f"open_items: {summary.get('open_item_count', 0)}")
    if result.get("results"):
        print(f"task_results: {len(result.get('results') or [])}")
    if delta:
        print(f"delta_status: {(delta.get('summary') or {}).get('status')}")
    if closeout:
        print(f"closeout_status: {closeout.get('status')}")


def print_acceptance_fix_plan_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    plan = result.get("fix_plan") or result.get("fix_plan_preview")
    plan = plan if isinstance(plan, dict) else {}
    review = result.get("outcome_review") if isinstance(result.get("outcome_review"), dict) else {}
    if review:
        print("MusicForge acceptance-fix-plan review")
        print(f"review: {summary.get('review_id') or review.get('review_id') or '-'}")
        print(f"plan: {summary.get('plan_id') or review.get('plan_id') or '-'}")
        print(f"sprint: {summary.get('fix_sprint_id') or review.get('fix_sprint_id') or '-'}")
        print(f"status: {summary.get('status') or review.get('status') or '-'}")
        print(f"effectiveness: {summary.get('plan_effectiveness_score') if summary.get('plan_effectiveness_score') is not None else '-'}")
        print(f"kb_helpfulness: {summary.get('kb_evidence_helpfulness') or '-'}")
        print(f"warnings: {summary.get('warning_count', 0)}")
        return
    print("MusicForge acceptance-fix-plan")
    print(f"plan: {summary.get('plan_id') or plan.get('plan_id') or '-'}")
    print(f"status: {summary.get('status') or plan.get('status') or '-'}")
    print(f"items: {summary.get('planned_item_count', 0)}")
    print(f"kb_matches: {summary.get('kb_match_count', 0)}")
    if result.get("fix_sprint"):
        print(f"created_fix_sprint: {(result.get('fix_sprint') or {}).get('fix_sprint_id')}")


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


def print_release_operations_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-operations")
    print(f"release: {result.get('release_id') or report.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or report.get('status') or '-'}")
    print(f"stage: {summary.get('current_stage') or report.get('current_stage') or '-'} -> {report.get('next_stage') or '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")
    board_summary = result.get("acceptance_board_summary") if isinstance(result.get("acceptance_board_summary"), dict) else {}
    board_verification = result.get("acceptance_board_verification") if isinstance(result.get("acceptance_board_verification"), dict) else {}
    if board_summary:
        print(f"acceptance board: {board_summary.get('readiness') or '-'} / accepted={board_summary.get('accepted_count', 0)}")
    if board_verification:
        print(f"acceptance board verify: {board_verification.get('status')}")
    signoff = result.get("acceptance_board_signoff") if isinstance(result.get("acceptance_board_signoff"), dict) else {}
    archive_verification = result.get("acceptance_board_signoff_archive_verification") if isinstance(result.get("acceptance_board_signoff_archive_verification"), dict) else {}
    if signoff:
        print(f"acceptance board signoff: {signoff.get('status')}")
    if result.get("acceptance_board_signoff_archive_zip"):
        print(f"acceptance board signoff archive zip: {(result.get('acceptance_board_signoff_archive_zip') or {}).get('sha256')}")
    if archive_verification:
        print(f"acceptance board signoff archive verify: {archive_verification.get('status')}")


def print_release_operations_runbook_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    manifest = result.get("manifest") if isinstance(result.get("manifest"), dict) else {}
    print("MusicForge release-operations-runbook")
    print(f"release: {result.get('release_id') or summary.get('release_id') or '-'}")
    print(f"runbook: {summary.get('runbook_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"safe: {summary.get('safe_count', 0)}")
    print(f"manual_required: {summary.get('manual_required_count', 0)}")
    print(f"failed: {summary.get('failed_count', 0)}")
    if manifest:
        print(f"export: {'stale' if manifest.get('stale') else 'current'}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_operations_signoff_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    gate = result.get("gate") if isinstance(result.get("gate"), dict) else {}
    print("MusicForge release-operations-signoff")
    print(f"release: {result.get('release_id') or summary.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"integrity: {summary.get('integrity_ok', False)}")
    if gate:
        print(f"gate: {gate.get('status')} signable={gate.get('signable')}")


def print_release_operations_archive_result(result: dict[str, Any]) -> None:
    manifest = result.get("manifest") if isinstance(result.get("manifest"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-operations-archive")
    print(f"release: {result.get('release_id') or manifest.get('release_id') or '-'}")
    if manifest:
        print(f"archive: {manifest.get('summary', {}).get('status') if isinstance(manifest.get('summary'), dict) else '-'}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_operations_audit_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-operations-audit")
    print(f"release: {result.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"entries: {summary.get('entry_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_operations_reviewer_pack_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-operations-reviewer-pack")
    print(f"release: {result.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"readiness: {summary.get('readiness') or '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_portfolio_audit_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    portfolio = result.get("portfolio") if isinstance(result.get("portfolio"), dict) else {}
    print("MusicForge release-portfolio-audit")
    print(f"portfolio: {result.get('portfolio_id') or portfolio.get('portfolio_id') or '-'}")
    print(f"status: {summary.get('status') or portfolio.get('status') or '-'}")
    print(f"releases: {summary.get('release_count', 0)}")
    print(f"risk_score: {summary.get('risk_score') if summary.get('risk_score') is not None else '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("portfolios") is not None:
        print(f"portfolios: {len(result.get('portfolios') or [])}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_portfolio_governance_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    queue = result.get("queue") if isinstance(result.get("queue"), dict) else {}
    print("MusicForge release-portfolio-governance-queue")
    print(f"queue: {result.get('queue_id') or queue.get('queue_id') or '-'}")
    print(f"portfolio: {queue.get('portfolio_id') or '-'}")
    print(f"status: {summary.get('status') or queue.get('status') or '-'}")
    print(f"items: {summary.get('total_items', 0)}")
    print(f"safe_completed: {summary.get('safe_completed', 0)}")
    print(f"manual_required: {summary.get('manual_required', 0)}")
    print(f"blocked: {summary.get('blocked', 0)}")
    print(f"failed: {summary.get('failed', 0)}")
    if result.get("queues") is not None:
        print(f"queues: {len(result.get('queues') or [])}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_portfolio_governance_signoff_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    archive = result.get("archive_summary") if isinstance(result.get("archive_summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-signoff")
    print(f"queue: {result.get('queue_id') or summary.get('queue_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"integrity: {summary.get('integrity_ok', False)}")
    if archive:
        print(f"archive: {archive.get('status') or '-'}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_portfolio_governance_audit_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-audit")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"entries: {summary.get('entry_count', 0)}")
    print(f"queues: {summary.get('queue_count', 0)}")
    print(f"signed_queues: {summary.get('signed_queue_count', 0)}")
    print(f"archive_verified: {summary.get('archive_verified_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_portfolio_governance_reviewer_pack_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-reviewer-pack")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"audit: {summary.get('audit_status') or '-'}")
    print(f"queues: {summary.get('queue_count', 0)}")
    print(f"signed_queues: {summary.get('signed_queue_count', 0)}")
    print(f"archive_verified: {summary.get('archive_verified_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_portfolio_governance_final_board_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    signoff = result.get("signoff_summary") if isinstance(result.get("signoff_summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-final-board")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"reviewer_response: {summary.get('reviewer_response_status') or '-'}")
    print(f"audit: {summary.get('audit_verification_status') or '-'}")
    print(f"reviewer_pack: {summary.get('reviewer_pack_verification_status') or '-'}")
    print(f"signoff: {signoff.get('status') or '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_portfolio_governance_evidence_vault_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-evidence-vault")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"final_board: {summary.get('final_board_signoff_status') or '-'}")
    print(f"nested_required: {summary.get('required_package_count', 0)}")
    print(f"nested_current: {summary.get('current_required_package_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_portfolio_governance_attestation_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    certificate = result.get("certificate") if isinstance(result.get("certificate"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-attestation")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"profile: {result.get('profile') or summary.get('profile') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"certificate: {certificate.get('certificate_id') or summary.get('certificate_id') or '-'}")
    print(f"vault: {summary.get('vault_verification_status') or '-'} / deep {summary.get('deep_verification_status') or '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_portfolio_governance_attestation_registry_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    entry = result.get("entry") if isinstance(result.get("entry"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-attestation-registry")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"profile: {result.get('profile') or summary.get('profile') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"current entry: {summary.get('current_entry_id') or '-'}")
    print(f"entries: {summary.get('entry_count', 0)}")
    print(f"published: {summary.get('published_count', 0)}")
    print(f"revoked: {summary.get('revoked_count', 0)}")
    if entry:
        print(f"entry: {entry.get('entry_id') or '-'} / {entry.get('status') or '-'}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_portfolio_governance_attestation_portal_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-attestation-portal")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"profile: {result.get('profile') or summary.get('profile') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"current entry: {summary.get('current_entry_id') or '-'}")
    print(f"current certificate: {summary.get('current_certificate_id') or '-'}")
    print(f"registry: {summary.get('registry_status') or '-'}")
    print(f"attestation: {summary.get('attestation_status') or '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def print_release_portfolio_governance_attestation_portal_review_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    response = result.get("response") if isinstance(result.get("response"), dict) else {}
    verification = result.get("verification") if isinstance(result.get("verification"), dict) else {}
    response_verification = result.get("response_verification") if isinstance(result.get("response_verification"), dict) else {}
    change = result.get("change_request") if isinstance(result.get("change_request"), dict) else {}
    print("MusicForge release-portfolio-governance-attestation-portal-review")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"profile: {result.get('profile') or summary.get('profile') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"review pack: {summary.get('review_pack_id') or '-'}")
    print(f"current entry: {summary.get('current_entry_id') or '-'}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify pack: {verification.get('status')}")
    if response:
        print(f"response: {response.get('response_id') or '-'} / {response.get('decision') or '-'}")
    if response_verification:
        print(f"verify response: {response_verification.get('status')}")
    if change:
        print(f"change request: {change.get('change_request_id') or '-'} / {change.get('status') or '-'}")


def print_release_portfolio_governance_attestation_accepted_evidence_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    evidence = result.get("accepted_evidence") if isinstance(result.get("accepted_evidence"), dict) else {}
    print("MusicForge release portfolio governance attestation accepted evidence")
    print(f"portfolio: {result.get('portfolio_id')}")
    print(f"status: {summary.get('status') or evidence.get('status') or 'missing'}")
    print(f"external review: {summary.get('external_review_status') or 'missing'}")
    print(f"accepted evidence: {summary.get('accepted_evidence_id') or evidence.get('accepted_evidence_id') or '-'}")
    print(f"response: {summary.get('response_id') or '-'}")
    if result.get("verification"):
        print(f"verification: {result.get('verification', {}).get('status')}")


def print_release_portfolio_governance_attestation_transparency_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    print("MusicForge release portfolio governance attestation transparency")
    print(f"portfolio: {result.get('portfolio_id')}")
    print(f"status: {summary.get('status') or 'missing'}")
    print(f"current entry: {summary.get('current_entry_id') or '-'}")
    print(f"external review: {summary.get('external_review_status') or 'missing'}")
    print(f"events: {summary.get('event_count', 0)}")
    print(f"notices: {summary.get('notice_count', 0)}")
    if result.get("verification"):
        print(f"verification: {result.get('verification', {}).get('status')}")


def print_release_portfolio_governance_attestation_transparency_acknowledgement_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    evidence_summary = result.get("evidence_summary") if isinstance(result.get("evidence_summary"), dict) else {}
    response = result.get("response") if isinstance(result.get("response"), dict) else {}
    print("MusicForge release portfolio governance attestation transparency acknowledgement")
    print(f"portfolio: {result.get('portfolio_id')}")
    print(f"pack: {summary.get('status') or 'missing'} / {summary.get('pack_id') or '-'}")
    if response:
        print(f"response: {response.get('response_id') or '-'} / {response.get('status') or '-'}")
    if evidence_summary:
        print(f"evidence: {evidence_summary.get('status') or 'missing'} / {evidence_summary.get('acknowledgement_id') or '-'}")
    if result.get("pack_verification"):
        print(f"pack verification: {result.get('pack_verification', {}).get('status')}")
    if result.get("evidence_verification"):
        print(f"evidence verification: {result.get('evidence_verification', {}).get('status')}")
    if result.get("change_request"):
        change = result["change_request"]
        print(f"change request: {change.get('change_request_id') or '-'} / {change.get('status') or '-'}")


def print_public_trust_center_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification") if isinstance(result.get("verification"), dict) else {}
    print("MusicForge public-trust-center")
    print(f"center: {result.get('center_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"readiness: {summary.get('readiness') or '-'}")
    print(f"stale: {summary.get('stale', result.get('stale', False))}")
    print(f"releases: {summary.get('release_count', 0)}")
    print(f"portfolios: {summary.get('portfolio_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('sha256') or (result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")


def _build_release_portfolio_governance_attestation_portal_store():
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore
    from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
    from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
    from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
    from song_agent.release_portfolio_governance_attestation import ReleasePortfolioGovernanceAttestationStore
    from song_agent.release_portfolio_governance_attestation_portal import ReleasePortfolioGovernanceAttestationPortalStore
    from song_agent.release_portfolio_governance_attestation_registry import ReleasePortfolioGovernanceAttestationRegistryStore
    from song_agent.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore
    from song_agent.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore
    from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore
    from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore

    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
    governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
    governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
    final_board_store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
    vault_store = ReleasePortfolioGovernanceEvidenceVaultStore(
        portfolio_store=portfolio_store,
        governance_store=governance_store,
        signoff_store=governance_signoff_store,
        audit_store=governance_audit_store,
        reviewer_pack_store=governance_reviewer_store,
        final_board_store=final_board_store,
    )
    attestation_store = ReleasePortfolioGovernanceAttestationStore(portfolio_store=portfolio_store, final_board_store=final_board_store, evidence_vault_store=vault_store)
    registry_store = ReleasePortfolioGovernanceAttestationRegistryStore(attestation_store=attestation_store)
    return ReleasePortfolioGovernanceAttestationPortalStore(registry_store=registry_store, attestation_store=attestation_store)


def _build_public_trust_center_store():
    from song_agent.public_trust_center import PublicTrustCenterStore
    from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore
    from song_agent.release_portfolio_governance_attestation_portal_review import ReleasePortfolioGovernanceAttestationPortalReviewStore
    from song_agent.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore
    from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore

    portal_store = _build_release_portfolio_governance_attestation_portal_store()
    review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    accepted_store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
    transparency_store = ReleasePortfolioGovernanceAttestationTransparencyStore(
        attestation_store=portal_store.attestation_store,
        registry_store=portal_store.registry_store,
        portal_store=portal_store,
        accepted_evidence_store=accepted_store,
    )
    acknowledgement_store = ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore(transparency_store=transparency_store)
    portfolio_store = portal_store.attestation_store.portfolio_store
    return PublicTrustCenterStore(
        release_store=portfolio_store.release_store,
        portfolio_store=portfolio_store,
        registry_store=portal_store.registry_store,
        portal_store=portal_store,
        transparency_store=transparency_store,
        acknowledgement_store=acknowledgement_store,
        distribution_store=portfolio_store.operations_store.distribution_store,
        submission_store=portfolio_store.operations_store.submission_store,
        submission_evidence_store=portfolio_store.operations_store.submission_evidence_store,
        operations_store=portfolio_store.operations_store,
        operations_runbook_store=portfolio_store.runbook_store,
        operations_signoff_store=portfolio_store.signoff_store,
        operations_audit_store=portfolio_store.audit_store,
        operations_reviewer_pack_store=portfolio_store.reviewer_pack_store,
    )


def _build_public_trust_center_publication_store():
    from song_agent.public_trust_center_acceptance_board import PublicTrustCenterAcceptanceBoardStore
    from song_agent.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStore
    from song_agent.public_trust_center_anchor_transparency import PublicTrustCenterAnchorTransparencyStore
    from song_agent.public_trust_center_distribution_kit import PublicTrustCenterDistributionKitStore
    from song_agent.public_trust_center_distribution_kit_acceptance import PublicTrustCenterDistributionKitAcceptanceStore
    from song_agent.public_trust_center_publication import PublicTrustCenterPublicationStore

    trust_store = _build_public_trust_center_store()
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=trust_store)
    anchor_transparency_store = PublicTrustCenterAnchorTransparencyStore(anchor_registry_store=anchor_store)
    distribution_kit_store = PublicTrustCenterDistributionKitStore(
        trust_center_store=trust_store,
        anchor_registry_store=anchor_store,
        anchor_transparency_store=anchor_transparency_store,
    )
    acceptance_store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=distribution_kit_store)
    board_store = PublicTrustCenterAcceptanceBoardStore(acceptance_store=acceptance_store)
    return PublicTrustCenterPublicationStore(
        trust_center_store=trust_store,
        distribution_kit_store=distribution_kit_store,
        anchor_registry_store=anchor_store,
        anchor_transparency_store=anchor_transparency_store,
        acceptance_store=acceptance_store,
        acceptance_board_store=board_store,
    )


def _acceptance_analytics_fail_on(readiness: str, fail_on: str | None) -> bool:
    if not fail_on:
        return False
    order = {"ready": 0, "watch": 1, "needs_work": 2, "blocked": 3, "empty": 0, "missing": 0}
    return order.get(readiness, 0) >= order.get(fail_on, 0)


def _writable_status(path: Path) -> str:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".musicforge-write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return "failed"
    return "ok"


def generate_request(
    request: SongRequest,
    *,
    out_dir: Path | None = None,
    resume: bool = False,
    force: bool = False,
    provider_config: ProviderConfig | None = None,
    provider_snapshot: dict | None = None,
    control: Callable[[str, str], None] | None = None,
    pipeline_mode: str = "single",
) -> tuple[Path, Path]:
    if resume and force:
        raise ValueError("--resume and --force cannot be used together.")
    if pipeline_mode not in {"single", "multinode"}:
        raise ValueError("pipeline_mode must be either single or multinode.")

    run_dir = out_dir or default_run_dir(request.title)
    if force and run_dir.exists():
        _reset_known_run_artifacts(run_dir)
    paths = ProjectPaths.create(run_dir)
    state = RunState(run_id=run_dir.name, request=request.to_dict())
    run_options = _run_options(provider_config, pipeline_mode)

    if resume:
        _ensure_resume_request_matches(paths, request)
        _ensure_resume_options_match(paths, run_options)

    runner = GraphRunner(
        _build_steps(
            paths,
            request,
            provider_config=provider_config,
            provider_snapshot=provider_snapshot,
            pipeline_mode=pipeline_mode,
            control=control,
            run_options=run_options,
        ),
        resume=resume,
        control=control,
    )
    try:
        runner.run(state, paths)
    except ResumeMismatchError as exc:
        raise ValueError(str(exc)) from exc

    return paths.data / "song-plan.json", paths.renders / "song.mid"


def _ensure_resume_request_matches(paths: ProjectPaths, request: SongRequest) -> None:
    request_path = paths.data / "request.json"
    if not request_path.exists():
        return

    existing_request = read_json(request_path)
    current_request = request.to_dict()
    if existing_request != current_request:
        raise ValueError(
            "Cannot resume this run because data/request.json does not match "
            "the current request. Use a new output directory or rerun with --force."
        )


def _ensure_resume_options_match(paths: ProjectPaths, run_options: dict[str, str]) -> None:
    options_path = paths.data / "run-options.json"
    if not options_path.exists():
        if run_options == {"generation_mode": "local", "pipeline_mode": "single"}:
            return
        raise ValueError(
            "Cannot resume this run because data/run-options.json is missing "
            "and the requested generation or pipeline mode is not the legacy "
            "local/single mode. Use a new output directory or rerun with --force."
        )

    existing_options = read_json(options_path)
    if existing_options != run_options:
        raise ValueError(
            "Cannot resume this run because data/run-options.json does not match "
            "the requested generation or pipeline mode. Use a new output directory "
            "or rerun with --force."
        )


def _reset_known_run_artifacts(run_dir: Path) -> None:
    for child_name in ("data", "renders", "logs", "stems"):
        child_path = run_dir / child_name
        if child_path.exists():
            shutil.rmtree(child_path)


def _build_steps(
    paths: ProjectPaths,
    request: SongRequest,
    *,
    provider_config: ProviderConfig | None = None,
    provider_snapshot: dict | None = None,
    pipeline_mode: str = "single",
    control: Callable[[str, str], None] | None = None,
    run_options: dict[str, str] | None = None,
) -> list[PipelineStep]:
    request_path = paths.data / "request.json"
    options_path = paths.data / "run-options.json"
    plan_path = paths.data / "song-plan.json"
    midi_path = paths.renders / "song.mid"
    provider_snapshot_path = paths.data / "provider-snapshot.json"
    compose_output_path = (
        paths.data / "nodes" / "song_plan_builder.json"
        if pipeline_mode == "multinode"
        else plan_path
    )

    def write_request(state: RunState, paths: ProjectPaths) -> None:
        write_json(request_path, request.to_dict())
        write_json(options_path, run_options or _run_options(provider_config, pipeline_mode))
        state.add_artifact(
            "request",
            ArtifactRef("json", str(request_path), "Normalized song request."),
        )
        state.add_artifact(
            "run_options",
            ArtifactRef("json", str(options_path), "Generation and pipeline mode options."),
        )

    def compose(state: RunState, paths: ProjectPaths) -> None:
        if pipeline_mode == "multinode":
            plan = generate_multinode_song_plan(
                request,
                provider_config=provider_config,
                provider_snapshot=provider_snapshot,
                node_store=NodeStore(paths.root),
                control=control,
            )
        elif provider_config is None:
            plan = SongAgent().generate(request)
        else:
            plan = generate_provider_song_plan(request, provider_config)
        write_json(plan_path, plan.to_dict())
        state.add_artifact(
            "song_plan",
            ArtifactRef("json", str(plan_path), "Structured song plan."),
        )
        if provider_snapshot is not None:
            write_json(provider_snapshot_path, provider_snapshot)
            state.add_artifact(
                "provider_snapshot",
                ArtifactRef("json", str(provider_snapshot_path), "Masked provider snapshot."),
            )

    def validate(state: RunState, paths: ProjectPaths) -> None:
        from song_agent.schemas.song import SongPlan

        plan = SongPlan.from_dict(read_json(plan_path))
        validate_song_plan(plan)

    def render(state: RunState, paths: ProjectPaths) -> None:
        from song_agent.schemas.song import SongPlan

        plan = SongPlan.from_dict(read_json(plan_path))
        render_midi(plan, midi_path)
        state.add_artifact("midi", ArtifactRef("midi", str(midi_path), "Rendered MIDI."))

    return [
        PipelineStep("normalize_request", request_path, write_request),
        PipelineStep(_compose_step_name(provider_config, pipeline_mode), compose_output_path, compose),
        PipelineStep("validate_song_plan", None, validate),
        PipelineStep("render_midi", midi_path, render),
    ]


def _compose_step_name(
    provider_config: ProviderConfig | None,
    pipeline_mode: str,
) -> str:
    if pipeline_mode == "multinode":
        return "multinode_compose"
    if provider_config is not None:
        return "provider_compose"
    return "deterministic_compose"


def _run_options(
    provider_config: ProviderConfig | None,
    pipeline_mode: str,
) -> dict[str, str]:
    return {
        "generation_mode": "provider" if provider_config is not None else "local",
        "pipeline_mode": pipeline_mode,
    }


if __name__ == "__main__":
    main()
