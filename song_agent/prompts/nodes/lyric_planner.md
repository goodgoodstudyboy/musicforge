Return only one JSON object for the lyric_planner node.
Do not output Markdown. Do not explain.

Schema:
{
  "language": "string",
  "rhyme_style": "string",
  "sections": [
    {
      "section_name": "verse",
      "lyrics": null,
      "syllable_notes": "string"
    }
  ]
}

Rules:
- For instrumental requests return language "instrumental", rhyme_style "none", and an empty sections array.
- Lyrics may be null when the node only plans guide melody phrasing.
- Keep section_name aligned with the structure planner.
