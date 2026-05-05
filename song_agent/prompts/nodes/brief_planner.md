Return only one JSON object for the brief_planner node.
Do not output Markdown. Do not explain.

Schema:
{
  "title": "string",
  "language": "string",
  "style": "string",
  "theme": "string",
  "duration_seconds": 180,
  "vocal_mode": "guide_melody",
  "tempo_bpm": 92,
  "key": "C major",
  "target_listener": null,
  "use_case": null,
  "mood_tags": ["string"],
  "must_include": ["string"],
  "avoid": ["string"]
}

Rules:
- Preserve the request title, language, style, theme, vocal_mode, tempo_bpm, and key when present.
- Use a tempo between 40 and 240.
- Use a duration between 30 and 600 seconds.
