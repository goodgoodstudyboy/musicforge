Return only one JSON object for the harmony_planner node.
Do not output Markdown. Do not explain.

Schema:
{
  "key": "C major",
  "progressions": [
    {
      "section_name": "intro",
      "chords": ["Cmaj7", "Am7", "Dm7", "G7"]
    }
  ]
}

Rules:
- Keep chords simple enough for deterministic MIDI rendering.
- Every structure section must have one progression entry.
- Do not output note events.
