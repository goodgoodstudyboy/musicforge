Return only one JSON object for the style_planner node.
Do not output Markdown. Do not explain.

Schema:
{
  "genre_tags": ["string"],
  "instrumentation": ["string"],
  "lead_instrument": "string",
  "bass_style": "string",
  "drum_style": "string",
  "texture_notes": "string",
  "mix_notes": "string"
}

Rules:
- Keep instrumentation concise and MIDI-friendly.
- Include a lead, harmony/chord instrument, bass, and drums.
- Do not include vocals or audio rendering instructions.
