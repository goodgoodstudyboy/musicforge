# Music Review Guide

Automated checks can find empty songs, bad files, missing audio, and obvious
health failures. They cannot replace human listening.

## Review Modes

- `synthetic`: automated smoke evidence only.
- `manual`: a person played the MIDI or WAV and recorded the result.

Do not use synthetic review as release-ready human approval.

## What To Listen For

For every manual review, confirm:

- The file plays from start to finish.
- The output is not empty or silent.
- There is no obvious clipping, distortion, or long unintended silence.
- The main melody or lead idea is perceptible.
- Drum, bass, harmony, and lead parts are not obviously misaligned.
- Sections have audible contrast where the arrangement claims intro, verse,
  chorus, bridge, or outro.
- A Regression Songbook batch does not collapse into one identical-sounding
  pattern.

## Recording Findings

Use Studio to mark each case as accepted, needs fix, or rejected. When there is
a concrete issue, add a marker with time, category, severity, and notes. Markers
can feed ReviewTask, Mix Patch, or Audio Revision workflows, but applying a fix
remains an explicit manual step.

