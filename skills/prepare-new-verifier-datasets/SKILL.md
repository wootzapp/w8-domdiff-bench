---
name: prepare-new-verifier-datasets
description: Prepare paired screenshot and DOM-diff datasets from one recorded task under data-new-dom, with Microsoft-compatible task metadata, final answers, and modality-specific web_surfer.log files.
---

# Prepare New Verifier Datasets

Prepare exactly one logical task at a time. Convert the recorded source at
data-new-dom/<task-id>/ into two verifier inputs:

- data-new-screenshot/<task-id>/
- data-new-short-dom/<task-id>/

Never modify, rename, delete, or clean up the source under data-new-dom.
Do not generate rubrics, scores, verifier outputs, commits, or pushes as part
of this skill. Those are separate workflows.

## Required output layouts

The screenshot dataset is flat and contains only:

    data-new-screenshot/<task-id>/
    ├── task_data.json
    ├── web_surfer.log
    ├── final_answer.json
    ├── screenshot0.png
    ├── screenshot1.png
    └── ... screenshotN.png

The DOM-diff dataset is flat and contains only:

    data-new-short-dom/<task-id>/
    ├── task_data.json
    ├── web_surfer.log
    ├── final_answer.json
    ├── dom_diff1.txt
    ├── dom_diff2.txt
    └── ... dom_diffN.txt

Do not add nested source folders, duplicate frames, screenshot_manifest.json,
rubric files, score folders, or other intermediate artifacts.

## Source audit

Before copying anything, inspect the complete source task. Locate the task
instruction and starting URL, ordered actions, action arguments, timestamps,
thoughts, URLs, final answer, abort status, screenshots, and DOM-diff files.
Use recorded values; never invent coordinates, URLs, text, keys, pixels,
timestamps, action arguments, or answers merely to fill a schema. If required
evidence is absent or ambiguous, stop and report it.

Read source steps in numeric order, not lexical order. Preserve every recorded
action, including scrolls, no-op actions, and actions whose state did not
visibly change. Never mix frames or logs from another task.

## State and screenshot alignment

Let N be the number of ordered DOM-diff transitions in the source.

1. Copy exactly those transitions as dom_diff1.txt through dom_diffN.txt.
2. Create exactly N + 1 screenshots: screenshot0.png is the initial state,
   and screenshot{i}.png is the after-state for transition i.
3. Preserve equal-looking images when they correspond to different states; do
   not deduplicate by hash or filename.
4. Do not silently drop actions to make counts fit. If the source has an
   action/state mismatch, report it instead of fabricating evidence.
5. Validate one unambiguous before/after relation and one aligned after frame
   for every transition.

## task_data.json

Write one JSON list containing one task record, preserving task identity and
instruction:

    [
      {
        "task_id": "<task-id>",
        "confirmed_task": "<exact recorded instruction>",
        "website": "<recorded starting URL>",
        "level": "manual_new_verifier_task"
      }
    ]

Use the source level when meaningful; otherwise use the shown fallback. The
paired datasets must have identical task metadata.

## final_answer.json

Preserve the recorded final answer and terminal status. For the screenshot
dataset, use:

    {
      "final_answer": "<exact recorded final answer>",
      "env_state_json": "<no_answer>",
      "env_state_raw": "<no_answer>",
      "screenshots": ["screenshot0.png", "...", "screenshotN.png"],
      "is_aborted": false,
      "is_rel_paths": true,
      "token_usage": {}
    }

List every relative frame path in order in `screenshots`, from screenshot0.png
through screenshotN.png.

For the DOM-diff dataset, use:

    {
      "final_answer": "<exact recorded final answer>",
      "env_state_json": "<no_answer>",
      "env_state_raw": "<no_answer>",
      "is_aborted": false,
      "is_rel_paths": true,
      "token_usage": {}
    }

Omit the `screenshots` key entirely from the DOM-diff `final_answer.json`; do
not set it to an empty list. The DOM verifier loader does not consume that
field. Do not change a real recorded answer to make it agree with the task.

## web_surfer.log

Write one valid JSON object per line, in recorded action order. Each line
retains the Microsoft-compatible event envelope and recorded timestamp,
action, arguments, thought/message, and URL when present:

    {
      "timestamp": "<recorded timestamp>",
      "type": "WebSurferEvent",
      "source": "WebSurfer",
      "message": "<recorded thought/action message>",
      "action": "<normalized action>",
      "arguments": {"<action arguments>": "<recorded values>"},
      "url": "<recorded URL or empty string>"
    }

Use the verifier's existing normalization (navigation → visit_url, click →
left_click, typing → type, key press → key, scroll → scroll). Keep recorded
coordinates, keys, text, flags, and scroll pixels unless a modality rule
removes them. URLs come from recorded after-state, then recorded before-state;
never invent a URL.

### DOM-diff log

The DOM-diff log contains all recorded action information except coordinates.
Remove coordinate-like fields wherever they occur, including x, y,
coordinate, point, and coordinate objects nested in target or arguments.
Keep non-coordinate target/reference semantics, text, keys, scroll pixels,
thoughts, timestamps, and URLs.

### Screenshot log

The screenshot log contains all recorded action information except the target
parameter. Remove only target fields, including nested target parameters;
retain recorded coordinates and every other argument.

Both logs must have the same event count, order, and timestamps. Their only
intentional difference is the modality-specific field removal.

## Validation before completion

Run read-only validation and report paths, counts, and results. All checks
must pass:

- Every JSON file parses and every log line parses independently.
- Both task records match the source and each other.
- There are N contiguous diff files and exactly N + 1 screenshots.
- Screenshot numbering starts at zero with no gaps; every frame exists.
- Every diff/action/state transition aligns to its corresponding after frame.
- DOM-diff final answers do not contain a `screenshots` key.
- DOM-diff logs have no coordinate fields; screenshot logs have no target
  fields and retain coordinates.
- Paired logs have aligned action order and timestamps.
- Final answer and abort status match the source.
- data-new-dom has no filesystem or content changes.

Stop on a failed check; do not repair it by fabricating data. Do not run a
verifier or generate rubrics unless separately requested.
