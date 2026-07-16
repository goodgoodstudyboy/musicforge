from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

from pathlib import Path
from typing import Any

from song_agent.domains.quality.audio_campaigns import AudioCampaignStore
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.project_repository import now_iso
from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash


AUDIO_CAMPAIGN_ANALYTICS_SCHEMA_VERSION = 1


class AudioCampaignAnalyticsStore:
    def __init__(self, campaign_store: AudioCampaignStore | None = None) -> None:
        self.campaign_store = campaign_store or AudioCampaignStore()

    def analytics_dir(self, campaign_id: str) -> Path:
        return self.campaign_store.campaign_dir(campaign_id) / "analytics"

    def report_path(self, campaign_id: str) -> Path:
        return self.analytics_dir(campaign_id) / "analytics-report.json"

    def refresh(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.campaign_store.read_campaign(campaign_id)
        report = self.campaign_store.refresh_report(campaign_id)
        analytics = build_audio_campaign_analytics(campaign, report)
        write_json(self.report_path(campaign_id), analytics)
        return analytics

    def read(self, campaign_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.report_path(campaign_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(f"Audio Campaign analytics report not found: {campaign_id}.")
        return read_json(path)


def build_audio_campaign_analytics(campaign: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    cases = campaign.get("cases") if isinstance(campaign.get("cases"), list) else []
    issue_counts: dict[str, dict[str, Any]] = {}
    fix_effectiveness: list[dict[str, Any]] = []
    ratings: list[int] = []
    high_count = 0
    critical_count = 0
    fixed_count = 0
    recheck_passed = 0
    for case in cases:
        if not isinstance(case, dict):
            continue
        review = case.get("review") if isinstance(case.get("review"), dict) else {}
        rating = _safe_int(review.get("rating"))
        if rating:
            ratings.append(rating)
        markers = [item for item in case.get("markers", []) if isinstance(item, dict)]
        for marker in markers:
            category = str(marker.get("category") or "uncategorized")
            severity = str(marker.get("severity") or "note")
            row = issue_counts.setdefault(category, {"category": category, "count": 0, "severity_max": severity, "fixed_count": 0})
            row["count"] += 1
            row["severity_max"] = _max_severity(str(row.get("severity_max") or ""), severity)
            if severity == "high":
                high_count += 1
            if severity == "critical":
                critical_count += 1
        fix = case.get("fix") if isinstance(case.get("fix"), dict) else {}
        if fix.get("fix_sprint_id"):
            fixed_count += 1
            if str(review.get("status") or "") == "accepted":
                recheck_passed += 1
            for marker in markers:
                category = str(marker.get("category") or "uncategorized")
                if category in issue_counts:
                    issue_counts[category]["fixed_count"] += 1
            fix_effectiveness.append(
                {
                    "case_id": case.get("case_id"),
                    "fix_sprint_id": fix.get("fix_sprint_id"),
                    "before_rating": rating,
                    "after_rating": rating,
                    "status": "effective" if str(review.get("status") or "") == "accepted" else "needs_review",
                }
            )
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    case_count = _safe_int(summary.get("case_count")) or len(cases)
    needs_fix_count = _safe_int(summary.get("needs_fix_count"))
    analytics = sanitize_metadata(
        {
            "schema_version": AUDIO_CAMPAIGN_ANALYTICS_SCHEMA_VERSION,
            "campaign_id": campaign.get("campaign_id"),
            "generated_at": now_iso(),
            "status": "passed" if report.get("status") == "passed" else "warning",
            "source": {
                "campaign_source_hash": campaign.get("source_hash"),
                "campaign_report_hash": report.get("integrity_hash"),
            },
            "summary": {
                "case_count": case_count,
                "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
                "needs_fix_rate": round(needs_fix_count / case_count, 4) if case_count else 0,
                "recheck_pass_rate": round(recheck_passed / fixed_count, 4) if fixed_count else 1.0,
                "high_marker_count": high_count,
                "critical_marker_count": critical_count,
                "fixed_case_count": fixed_count,
            },
            "issue_taxonomy": sorted(issue_counts.values(), key=lambda row: (-int(row.get("count") or 0), str(row.get("category") or ""))),
            "style_weaknesses": [],
            "fix_effectiveness": fix_effectiveness,
            "recommendations": _recommendations(issue_counts),
        }
    )
    analytics["source_hash"] = stable_hash(analytics["source"])
    analytics["integrity_hash"] = _integrity_hash(analytics)
    return analytics


def _recommendations(issue_counts: dict[str, ImplementationDocument]) -> list[ImplementationDocument]:
    rows = []
    for item in sorted(issue_counts.values(), key=lambda row: -int(row.get("count") or 0))[:5]:
        rows.append({"priority": "medium", "message": f"Review recurring audio issue: {item.get('category')}.", "category": item.get("category")})
    return rows


def _max_severity(left: str, right: str) -> str:
    order = {"note": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    return left if order.get(left, 0) >= order.get(right, 0) else right


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})
