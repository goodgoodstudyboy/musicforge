from __future__ import annotations

from song_agent.platform.contracts import DomainDocument
from dataclasses import dataclass as dataclass
from typing import Any as Any

from song_agent.domains.creation.provider_edits import ProviderEditPatch as ProviderEditPatch
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan


@dataclass(frozen=True)
class CandidateScore:
    quality_overall: int
    validator: int
    patch_confidence: int
    novelty: int
    instruction_fit: int
    combined: int
    warnings: list[str]

    def to_dict(self) -> DomainDocument:
        return {
            "quality_overall": self.quality_overall,
            "validator": self.validator,
            "patch_confidence": self.patch_confidence,
            "novelty": self.novelty,
            "instruction_fit": self.instruction_fit,
            "combined": self.combined,
            "warnings": list(self.warnings),
        }


def score_provider_edit_candidate(
    *,
    parent_plan: SongPlan,
    candidate_plan: SongPlan,
    patch: ProviderEditPatch,
    validator_status: str = "passed",
) -> CandidateScore:
    quality_overall = int(candidate_plan.quality.scores.overall if candidate_plan.quality and candidate_plan.quality.scores else 0)
    validator = 100 if validator_status == "passed" else 0
    patch_confidence = round(max(0.0, min(1.0, patch.confidence)) * 100)
    novelty = _novelty_score(parent_plan, candidate_plan)
    instruction_fit = patch_confidence if patch_confidence else 60
    combined = round(
        quality_overall * 0.50
        + validator * 0.20
        + patch_confidence * 0.10
        + novelty * 0.10
        + instruction_fit * 0.10
    )
    warnings = []
    if validator_status != "passed":
        warnings.append("validator_failed")
    if novelty < 20:
        warnings.append("low_novelty")
    if quality_overall < 60:
        warnings.append("low_quality")
    return CandidateScore(
        quality_overall=quality_overall,
        validator=validator,
        patch_confidence=patch_confidence,
        novelty=novelty,
        instruction_fit=instruction_fit,
        combined=max(0, min(100, combined)),
        warnings=warnings,
    )


def rank_candidate_summaries(candidates: list[DomainDocument]) -> list[DomainDocument]:
    ready = [candidate for candidate in candidates if str(candidate.get("status") or "") == "ready"]
    ranked = sorted(
        ready,
        key=lambda candidate: (
            int((candidate.get("scores") or {}).get("combined") or 0),
            int((candidate.get("scores") or {}).get("quality_overall") or 0),
            str(candidate.get("candidate_id") or ""),
        ),
        reverse=True,
    )
    return [
        {
            "candidate_id": str(candidate.get("candidate_id")),
            "score": int((candidate.get("scores") or {}).get("combined") or 0),
            "rank": index + 1,
        }
        for index, candidate in enumerate(ranked)
    ]


def group_status_for_candidates(candidates: list[DomainDocument]) -> str:
    if not candidates:
        return "failed"
    statuses = {str(candidate.get("status") or "failed") for candidate in candidates}
    if statuses <= {"ready"}:
        return "ready"
    if "ready" in statuses:
        return "partial_ready"
    return "failed"


def _novelty_score(parent_plan: SongPlan, candidate_plan: SongPlan) -> int:
    parent = parent_plan.to_dict()
    candidate = candidate_plan.to_dict()
    changes = 0
    opportunities = 0

    for left, right in zip(parent.get("sections", []), candidate.get("sections", [])):
        opportunities += 3
        if left.get("chords") != right.get("chords"):
            changes += 1
        if left.get("lyrics") != right.get("lyrics"):
            changes += 1
        if left.get("bars") != right.get("bars"):
            changes += 1

    left_tracks = {track.get("name"): track for track in parent.get("tracks", [])}
    for right in candidate.get("tracks", []):
        opportunities += 1
        left = left_tracks.get(right.get("name"))
        if left is None or left.get("instrument") != right.get("instrument") or len(left.get("notes", [])) != len(right.get("notes", [])):
            changes += 1

    if opportunities <= 0:
        return 0
    ratio = changes / opportunities
    if ratio <= 0:
        return 0
    if ratio > 0.65:
        return 55
    if ratio > 0.35:
        return 85
    return max(20, round(ratio * 200))
