from __future__ import annotations

from song_agent.platform.contracts.coercion import as_document as _as_document
from song_agent.domains.legacy_documents import _as_int

from dataclasses import dataclass as dataclass
from typing import Any as Any

from song_agent.domains.creation.agent.pipeline import deterministic_compose as deterministic_compose
from song_agent.domains.creation.provider_contracts import ProviderRequestError as ProviderRequestError
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan, SongRequest as SongRequest


@dataclass
class MockProviderClient:
    mode: str = "ok"

    def test(self) -> dict[str, Any]:
        if self.mode == "request_error":
            raise ProviderRequestError("Mock provider request failed.")
        return {"ok": True, "message": "Mock provider test completed."}

    def generate_song_plan_json(self, request: SongRequest, config: Any) -> dict[str, Any]:
        if self.mode == "request_error":
            raise ProviderRequestError("Mock provider request failed.")
        if self.mode == "invalid_schema":
            return {"title": request.title}
        return deterministic_compose(request).to_dict()

    def generate_edit_patch_json(
        self,
        parent_plan: SongPlan,
        instruction: str,
        config: Any,
        prompt: str = "",
    ) -> dict[str, Any]:
        if self.mode == "request_error":
            raise ProviderRequestError("Mock provider request failed.")
        if self.mode == "invalid_schema":
            return {"schema_version": 1, "operations": [{"op": "write_file", "path": "C:/secret"}]}
        section_name = _target_section(parent_plan, instruction)
        lower = instruction.lower()
        if "chord" in lower or "harmony" in lower:
            operation: dict[str, Any] = {
                "op": "set_section_chords",
                "section_name": section_name,
                "chords": ["Cmaj7", "Am7", "Fmaj7", "G7"],
                "preserve": ["tempo", "key", "structure"],
            }
        elif _wants_lyric_rewrite(lower):
            operation = {
                "op": "rewrite_section_lyrics",
                "section_name": section_name,
                "lyrics": "A clearer hook line shaped by the provider edit",
                "preserve": ["tempo", "key", "structure", "harmony", "melody"],
            }
        elif "drum" in lower or "bass" in lower or "track" in lower:
            track_name = "drums" if "drum" in lower else "bass" if "bass" in lower else parent_plan.tracks[0].name
            operation = {
                "op": "set_track_density",
                "section_name": section_name,
                "track_name": track_name,
                "strength": 8 if _wants_lift(lower) else 3,
                "preserve": ["tempo", "key", "structure"],
            }
        else:
            operation = {
                "op": "set_section_energy",
                "section_name": section_name,
                "energy": 0.85 if _wants_lift(lower) else 0.3,
                "preserve": ["tempo", "key", "structure"],
            }
        return {
            "schema_version": 1,
            "summary": "Mock provider edit patch",
            "operations": [operation],
            "warnings": [],
            "confidence": 0.82,
        }

    def generate_edit_candidates_json(
        self,
        parent_plan: SongPlan,
        instruction: str,
        config: Any,
        candidate_count: int = 3,
        prompt: str = "",
    ) -> dict[str, Any]:
        if self.mode == "request_error":
            raise ProviderRequestError("Mock provider request failed.")
        if self.mode == "invalid_schema":
            return {"schema_version": 1, "candidates": [{"schema_version": 1, "operations": [{"op": "write_file", "path": "C:/secret"}]}]}
        count = max(2, min(5, int(candidate_count or 3)))
        variants = [
            {
                "summary": "Lift chorus energy",
                "operations": [
                    {
                        "op": "set_section_energy",
                        "section_name": _target_section(parent_plan, instruction),
                        "energy": 0.88,
                        "preserve": ["tempo", "key", "structure"],
                    }
                ],
                "confidence": 0.86,
            },
            {
                "summary": "Brighten chorus harmony",
                "operations": [
                    {
                        "op": "set_section_chords",
                        "section_name": _target_section(parent_plan, instruction),
                        "chords": ["Cmaj7", "Am7", "Fmaj7", "G7"],
                        "preserve": ["tempo", "key", "structure"],
                    }
                ],
                "confidence": 0.82,
            },
            {
                "summary": "Tighten rhythm section",
                "operations": [
                    {
                        "op": "set_track_density",
                        "section_name": _target_section(parent_plan, instruction),
                        "track_name": "drums",
                        "strength": 8,
                        "preserve": ["tempo", "key", "structure"],
                    }
                ],
                "confidence": 0.78,
            },
            {
                "summary": "Rewrite hook lyric",
                "operations": [
                    {
                        "op": "rewrite_section_lyrics",
                        "section_name": _target_section(parent_plan, instruction),
                        "lyrics": "A brighter hook line shaped for the final lift",
                        "preserve": ["tempo", "key", "structure", "harmony"],
                    }
                ],
                "confidence": 0.74,
            },
            {
                "summary": "Add arrangement variation",
                "operations": [
                    {
                        "op": "arrangement_variation",
                        "section_name": _target_section(parent_plan, instruction),
                        "track_name": "melody",
                        "instrument": "lead synth",
                        "strength": 7,
                        "preserve": ["tempo", "key", "structure"],
                    }
                ],
                "confidence": 0.70,
            },
        ]
        return {
            "schema_version": 1,
            "candidates": [
                {"schema_version": 1, "warnings": [], **variant}
                for variant in variants[:count]
            ],
        }

    def generate_review_judge_json(
        self,
        parent_plan: SongPlan,
        judge_payload: dict[str, Any],
        config: Any,
        prompt: str = "",
    ) -> dict[str, Any]:
        if self.mode == "request_error":
            raise ProviderRequestError("Mock provider request failed.")
        candidates = [item for item in judge_payload.get("candidates", []) if isinstance(item, dict)]
        if self.mode == "invalid_schema":
            return {
                "recommended_candidate_id": "../../provider.json",
                "candidate_scores": [],
                "comparison_summary": {},
                "manual_review_required": True,
            }
        if not candidates:
            return {
                "recommended_candidate_id": "",
                "candidate_scores": [],
                "comparison_summary": {},
                "manual_review_required": True,
                "warnings": ["no ready candidates"],
            }
        scores: list[dict[str, Any]] = []
        for index, candidate in enumerate(candidates):
            candidate_id = str(candidate.get("candidate_id") or "")
            local_scores = _as_document(candidate.get("scores"))
            combined = _as_int(local_scores.get("combined") or max(60, 86 - index * 6))
            provider_bonus = 3 if candidate.get("source") == "provider" else 0
            overall = max(0, min(100, combined + provider_bonus - index))
            risk = max(5, min(95, _as_int(local_scores.get("risk") or (18 + index * 7))))
            scores.append(
                {
                    "candidate_id": candidate_id,
                    "overall": overall,
                    "review_fit": max(0, min(100, overall + 2)),
                    "target_precision": max(0, min(100, overall - 1)),
                    "musicality": max(0, min(100, overall)),
                    "novelty": max(0, min(100, 58 + index * 6)),
                    "risk": risk,
                    "confidence": round(max(0.35, min(0.92, 0.86 - index * 0.05)), 2),
                    "reason": f"Mock judge finds {candidate_id} balances the review target with manageable risk.",
                    "risks": ["higher_arrangement_risk"] if risk >= 70 else [],
                }
            )
        recommended = sorted(scores, key=lambda item: (-int(item["overall"]), int(item["risk"]), str(item["candidate_id"])))[0]
        return {
            "data": {
                "recommended_candidate_id": recommended["candidate_id"],
                "candidate_scores": scores,
                "comparison_summary": {
                    "best_candidate_id": recommended["candidate_id"],
                    "reason": "Best balance of review fit, target precision, and manageable risk.",
                    "tradeoffs": [],
                },
                "manual_review_required": True,
                "warnings": [],
            },
            "usage": {
                "prompt_tokens": 88 + 12 * len(candidates),
                "completion_tokens": 46 + 10 * len(candidates),
                "total_tokens": 134 + 22 * len(candidates),
            },
            "request_id": "mock-review-judge",
        }

    def generate_node_json(
        self,
        node_name: str,
        node_input: dict[str, Any],
        config: Any,
        prompt: str = "",
    ) -> dict[str, Any]:
        if self.mode == "request_error":
            raise ProviderRequestError("Mock provider request failed.")
        if self.mode == "invalid_schema":
            return {"node": node_name}
        if node_name == "brief_planner":
            request = node_input.get("request", {})
            return {
                "title": request.get("title", "Mock Song"),
                "language": request.get("language", "en"),
                "style": request.get("style", "pop"),
                "theme": request.get("theme", "mock theme"),
                "duration_seconds": request.get("duration_seconds", 180),
                "vocal_mode": request.get("vocal_mode", "guide_melody"),
                "tempo_bpm": request.get("tempo_bpm") or 92,
                "key": request.get("key") or "C major",
                "target_listener": None,
                "use_case": "mock provider node",
                "mood_tags": _style_tags(str(request.get("style", "pop")))[:4],
                "must_include": [],
                "avoid": [],
            }
        if node_name == "style_planner":
            brief = node_input.get("brief", {})
            tags = _style_tags(str(brief.get("style", "pop"))) or ["pop"]
            return {
                "genre_tags": tags,
                "instrumentation": ["lead synth", "electric piano", "electric bass", "gm drums"],
                "lead_instrument": "lead synth",
                "bass_style": "electric bass",
                "drum_style": "tight acoustic kit",
                "texture_notes": f"Mock texture for {brief.get('theme', 'theme')}",
                "mix_notes": "Mock provider node output.",
            }
        if node_name == "structure_planner":
            return {
                "meter": "4/4",
                "sections": [
                    {
                        "name": "intro",
                        "start_bar": 1,
                        "bars": 4,
                        "energy": 2,
                        "purpose": "set mood",
                        "tension": 2,
                        "density": 2,
                        "role": "establish",
                        "transition": "open into verse",
                        "hook_candidate": False,
                    },
                    {
                        "name": "verse",
                        "start_bar": 5,
                        "bars": 8,
                        "energy": 4,
                        "purpose": "state idea",
                        "tension": 4,
                        "density": 4,
                        "role": "narrative",
                        "transition": "build toward hook",
                        "hook_candidate": False,
                    },
                    {
                        "name": "chorus",
                        "start_bar": 13,
                        "bars": 8,
                        "energy": 7,
                        "purpose": "hook",
                        "tension": 6,
                        "density": 7,
                        "role": "hook",
                        "transition": "land the hook",
                        "hook_candidate": True,
                    },
                    {
                        "name": "outro",
                        "start_bar": 21,
                        "bars": 4,
                        "energy": 3,
                        "purpose": "resolve",
                        "tension": 2,
                        "density": 3,
                        "role": "resolve",
                        "transition": "reduce density",
                        "hook_candidate": False,
                    },
                ],
            }
        if node_name == "lyric_planner":
            brief = node_input.get("brief", {})
            structure = node_input.get("structure", {})
            if brief.get("vocal_mode") == "instrumental":
                return {"language": "instrumental", "rhyme_style": "none", "sections": []}
            return {
                "language": brief.get("language", "en"),
                "rhyme_style": "loose",
                "sections": [
                    {
                        "section_name": section.get("name", "section"),
                        "lyrics": None,
                        "syllable_notes": "mock guide melody",
                    }
                    for section in structure.get("sections", [])
                ],
            }
        if node_name == "harmony_planner":
            brief = node_input.get("brief", {})
            structure = node_input.get("structure", {})
            return {
                "key": brief.get("key", "C major"),
                "progressions": [
                    {
                        "section_name": section.get("name", "section"),
                        "chords": ["Cmaj7", "Am7", "Dm7", "G7"],
                    }
                    for section in structure.get("sections", [])
                ],
            }
        return {}


def _style_tags(style: str) -> list[str]:
    return [tag.strip().lower() for tag in style.split(",") if tag.strip()]


def _target_section(parent_plan: SongPlan, instruction: str) -> str:
    lower = instruction.lower()
    sections = [section.name for section in parent_plan.sections]
    if "final" in lower or "最后" in lower:
        for section in reversed(sections):
            if "chorus" in section.lower():
                return section
    for section in sections:
        if section.lower() in lower:
            return section
    for section in sections:
        if "chorus" in section.lower():
            return section
    return sections[0]


def _wants_lift(lower_instruction: str) -> bool:
    return any(word in lower_instruction for word in ("more", "lift", "strong", "energetic", "燃", "增强", "更"))


def _wants_lyric_rewrite(lower_instruction: str) -> bool:
    if "keep lyrics" in lower_instruction or "不要改歌词" in lower_instruction:
        return False
    return any(word in lower_instruction for word in ("rewrite", "change lyrics", "hook text", "文案", "改歌词", "重写歌词"))
