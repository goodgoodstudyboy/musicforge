from __future__ import annotations

import argparse
import json
import shutil
import sys
import os
from pathlib import Path
from collections.abc import Callable

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
    verify_parser.add_argument("--deep", action="store_true", help="Run the Distribution Package verifier on nested target ZIP files.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=1024, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=4096, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=10000, help="Maximum number of ZIP entries.")
    return verify_parser


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


def main() -> None:
    try:
        _main()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


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
    elif raw_args and raw_args[0] == "release-check":
        from song_agent.release_checks import print_release_check_report, run_release_checks

        report = run_release_checks()
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
