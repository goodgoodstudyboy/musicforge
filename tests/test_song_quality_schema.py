import pytest

from song_agent.schemas.song import (
    MotifPlan,
    QualityScores,
    SectionIntent,
    SongPlan,
    SongQualityMeta,
)
from tests.test_song_plan import make_valid_plan


def test_song_plan_accepts_missing_quality() -> None:
    data = make_valid_plan().to_dict()
    data.pop("quality", None)

    plan = SongPlan.from_dict(data)

    assert plan.quality is None


def test_quality_metadata_round_trips() -> None:
    plan = make_valid_plan()
    quality = SongQualityMeta(
        summary="Quality summary",
        primary_motif=MotifPlan(
            name="hook",
            description="rising phrase",
            rhythm_pattern=[1.0, 0.5],
            pitch_intervals=[0, 3],
            anchor_section="chorus",
        ),
        section_intents=[
            SectionIntent("intro", "establish", 2, 2, 2),
            SectionIntent("chorus", "hook", 7, 6, 7, hook=True),
        ],
        hook_sections=["chorus"],
        scores=QualityScores(82, 80, 84, 78, 86, 70),
        warnings=["warning"],
    )
    plan = SongPlan(plan.title, plan.key, plan.tempo_bpm, plan.meter, plan.sections, plan.tracks, quality)

    restored = SongPlan.from_dict(plan.to_dict())

    assert restored.quality is not None
    assert restored.quality.primary_motif is not None
    assert restored.quality.primary_motif.name == "hook"
    assert restored.quality.section_intents[1].hook is True
    assert restored.quality.scores is not None
    assert restored.quality.scores.overall == 82


def test_quality_scores_validate_range() -> None:
    data = make_valid_plan().to_dict()
    data["quality"] = {
        "scores": {
            "overall": 101,
            "structure": 80,
            "melody": 80,
            "harmony": 80,
            "arrangement": 80,
        }
    }

    with pytest.raises(ValueError, match="overall must be between 0 and 100"):
        SongPlan.from_dict(data)


def test_section_intent_validates_range() -> None:
    data = make_valid_plan().to_dict()
    data["quality"] = {
        "section_intents": [
            {
                "section_name": "chorus",
                "role": "hook",
                "energy": 11,
                "tension": 6,
                "density": 7,
            }
        ]
    }

    with pytest.raises(ValueError, match="energy must be between 0 and 10"):
        SongPlan.from_dict(data)
