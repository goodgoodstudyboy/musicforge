from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from song_agent.agent.pipeline import deterministic_compose
from song_agent.provider import ProviderRequestError
from song_agent.schemas.song import SongPlan, SongRequest


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
            operation = {
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
