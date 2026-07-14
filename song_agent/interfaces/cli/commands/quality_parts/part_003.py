from __future__ import annotations

from .dependencies import *

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

def build_release_audio_certification_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Release Audio Certification evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    refresh = subparsers.add_parser("refresh", help="Refresh Release Audio Certification report.")
    refresh.add_argument("release_id")
    status = subparsers.add_parser("status", help="Show Release Audio Certification status.")
    status.add_argument("release_id")
    signoff = subparsers.add_parser("signoff", help="Sign off a passed Release Audio Certification.")
    signoff.add_argument("release_id")
    signoff.add_argument("--signed-by", default="audio-certification")
    signoff.add_argument("--role", default="audio-certification-reviewer")
    signoff.add_argument("--reason", default="Release audio certification accepted.")
    export = subparsers.add_parser("export", help="Export Release Audio Certification package files.")
    export.add_argument("release_id")
    zip_cmd = subparsers.add_parser("zip", help="Build Release Audio Certification ZIP.")
    zip_cmd.add_argument("release_id")
    verify = subparsers.add_parser("verify", help="Verify Release Audio Certification ZIP.")
    verify.add_argument("release_id")
    verify.add_argument("--strict", action="store_true")
    verify.add_argument("--require-passed", action="store_true")
    verify.add_argument("--require-signed", action="store_true")
    verify.add_argument("--require-real-audio", action="store_true")
    verify.add_argument("--require-manual-review", action="store_true")
    verify.add_argument("--require-remediation-when-needed", action="store_true")
    verify.add_argument("--report-out", type=Path, default=None)
    return parser

__all__ = ('build_audio_fix_sprint_parser', 'build_audio_campaign_parser', 'build_verify_audio_campaign_parser', 'build_verify_audio_campaign_archive_parser', 'build_verify_audio_campaign_remediation_parser', 'build_release_audio_certification_parser')
