Return only one JSON object for the structure_planner node.
Do not output Markdown. Do not explain.

Schema:
{
  "meter": "4/4",
  "sections": [
    {
      "name": "intro",
      "start_bar": 1,
      "bars": 4,
      "energy": 2,
      "purpose": "string",
      "tension": 2,
      "density": 2,
      "role": "establish",
      "transition": "open into verse",
      "hook_candidate": false
    }
  ]
}

Rules:
- Use 4/4 only.
- start_bar values must be contiguous.
- bars must be positive.
- Keep the first version compact enough for MIDI rendering.
- energy, tension, and density must be integers from 0 to 10.
- Mark chorus or the strongest hook as hook_candidate true.
