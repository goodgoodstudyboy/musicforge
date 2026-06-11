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
    parser.add_argument("--profile", default="full", choices=["full", "quick", "latest", "v7", "publish"], help="Release-check profile to run.")
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
