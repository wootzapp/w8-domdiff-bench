---
name: prepare-verifier-datasets
description: Prepare matching screenshot-based and DOM-only datasets for exactly one logical Microsoft Universal Verifier task at a time. Use when converting one recorded browser-task folder containing actions.json, manifest.json, trajectory.jsonl, agent-browser records, before/after screenshots, DOM snapshots, page states, DOM diffs, and verifier actions into paired parseable task_data.json, final_answer.json, web_surfer.log, sequential deduplicated screenshots, and screenshot-free DOM evidence without generating or editing rubric artifacts.
---

# Prepare Verifier Datasets

Create paired verifier inputs for exactly one logical task from recorded evidence without altering Microsoft verifier code, inventing task outcomes, or mixing rubric-generation artifacts into dataset preparation.

## Core rules

1. Treat recorded files as ground truth.
2. Inspect the complete source task before writing anything.
3. Preserve the source task until both derived datasets pass validation.
4. Derive action arguments, timestamps, URLs, task text, and final answer from recorded files. Never guess values that evidence can supply.
5. Create screenshot and DOM datasets in separate folders.
6. Use exact SHA-256 equality to remove duplicate screenshots while preserving chronological order.
7. Verify every retained screenshot belongs to the current task and expected site; exclude and document stale cross-task frames from a previous recording.
8. Keep every recorded action in `web_surfer.log`, even when its after-screenshot duplicates the preceding frame.
9. Remove screenshots from the DOM dataset only after the screenshot dataset is complete and verified.
10. Treat `task_data_with_canonical_rubric.json`, canonical rubric JSON/TSV files, rubric metrics, scores, and prior outputs as out of scope. Never create, edit, delete, copy, normalize, or require them. Preserve any existing copies byte-for-byte.
11. Never run the verifier, generate rubrics, call judge models, or create scores unless the user separately requests it.
12. Never modify `repo/fara/`, `repo/fara-dom-verifier/`, or other verifier source code during dataset preparation.

## Expected source evidence

Inspect all files recursively. Prefer these sources in this order:

- Task instruction: root `actions.json`; fall back to `manifest.json` or explicit user input.
- Ordered actions: root `trajectory.jsonl`.
- Action names and arguments: `trajectory.jsonl`, then `step_XXX/verifier_action.json`, `step_XXX/action.json`, and `step_XXX/interaction_capture.json`.
- Coordinates: recorded `trajectory.jsonl` coordinate, then `verifier_action.json`, then a recorded target box from DOM or interaction capture.
- Typed text and keys: `trajectory.jsonl` and agent-browser decision records.
- Timestamps: `trajectory.jsonl.started_at`.
- Before and after URLs: `trajectory.jsonl.before_page.url` and `after_page.url`; fall back to corresponding `page_state.json`.
- Final answer and completion status: `agent_browser_final.json`.
- Screenshots: `step_XXX/before/screenshot.png` and `step_XXX/after/screenshot.png`.
- Additional provenance: `manifest.json`, `agent_browser_decisions.jsonl`, and other root capture metadata.

Do not use DOM content to manufacture a more favorable final answer. Preserve what the recorded agent actually reported.

## Phase 1: Audit before conversion

1. Identify the exact source task and requested destination task number.
2. List root files, every `step_XXX` directory, and every screenshot.
3. Verify that step numbers are continuous and sort them numerically, never lexicographically.
4. Count trajectory actions and compare them with completed steps in the manifest.
5. Inspect `agent_browser_final.json` for `status`, `final_answer`, and termination details.
6. Inspect every trajectory action and record:
   - action number;
   - timestamp;
   - source action name;
   - text, key, URL, pixels, reference, and coordinate when present;
   - before URL and after URL;
   - whether the action visibly changed the state.
7. Hash all candidate screenshots before copying.
8. Record hashes of any pre-existing rubric-related files inside the destination task folders so the final audit can prove they were not changed.
9. Stop and report the gap if a non-fabricable value is absent. Do not silently invent coordinates, text, URLs, task instructions, final answers, or completion status.

Representational wrapper values may be normalized, such as destination task ID, WebSurfer event type, integer rounding of recorded coordinates, and relative screenshot paths.

## Phase 2: Build the screenshot dataset

Create:

```text
data-screenshot/taskN/
├── task_data.json
├── final_answer.json
├── web_surfer.log
├── screenshot_manifest.json
├── screenshot0.png
├── screenshot1.png
├── ...
├── actions.json
├── manifest.json
├── trajectory.jsonl
├── agent_browser_decisions.jsonl   # when present
└── agent_browser_final.json        # when present
```

Keep required verifier inputs at the task root. Copy root provenance files without changing their contents.

### Select screenshots

Use this deterministic sequence:

1. Start with `step_001/before/screenshot.png` as the initial state.
2. Visit `step_001/after/screenshot.png`, `step_002/after/screenshot.png`, and so on in numeric action order.
3. Compute SHA-256 for every candidate.
4. Copy a candidate only when its hash has not already been retained.
5. Name retained images continuously as `screenshot0.png`, `screenshot1.png`, ..., with no underscore, gaps, or duplicate contents.
6. Do not copy every step's before-screenshot. The preceding retained after-state already represents the next action's before-state unless capture evidence proves otherwise.
7. Before retaining the initial frame, confirm its associated page-state URL and visible site identity match the current task. If `step_001/before/screenshot.png` is stale evidence from another site, omit it, document the omission, and start numbering from the first task-aligned state.
8. Record every output-to-source mapping and every omitted duplicate in `screenshot_manifest.json`.
9. Preserve an action whose screenshot file was omitted. Keep image files unique, but record one action-aligned screenshot reference per action; reuse the retained path when consecutive actions have the same exact screenshot. The number of unique files may be smaller than the number of references.

Do not use filename similarity, image dimensions, or visual judgment for deduplication. Use exact hashes.

### Create `task_data.json`

Use a JSON list with one task:

```json
[
  {
    "task_id": "taskN",
    "confirmed_task": "Exact recorded task instruction",
    "website": "https://recorded-start-site.example/",
    "level": "manual_screenshot_task"
  }
]
```

- Use the destination folder identity for `task_id` to avoid collisions.
- Preserve the task's meaning exactly.
- Derive `website` from the instruction or first recorded navigation.
- Never add `precomputed_rubric` here and never create or edit `task_data_with_canonical_rubric.json`. Rubric freezing is a separate benchmark workflow.

### Create `final_answer.json`

The folder must contain exactly one lowercase file matching `*_answer.json`. Use `final_answer.json`:

```json
{
  "final_answer": "Exact agent_browser_final.json final answer",
  "env_state_json": "<no_answer>",
  "env_state_raw": "<no_answer>",
  "screenshots": [
    "screenshot0.png",
    "screenshot1.png"
  ],
  "is_aborted": false,
  "is_rel_paths": true,
  "token_usage": {}
}
```

- List screenshot references in action order. Provide at least one reference per recorded action because Microsoft strict loading requires every action to have a screenshot field.
- Reuse the same relative path when multiple actions share an exact duplicate frame; do not create duplicate image files merely to increase the reference count.
- Set `is_aborted` only when the run was actually aborted. A normal termination with `status: failure` is not automatically an abort.
- Do not fabricate environment state or token usage.
- Do not create a second lowercase `*_answer.json` file.

### Create `web_surfer.log`

Write one valid JSON object per line in chronological action order. Use this structure:

```json
{"timestamp":"RECORDED_TIME","type":"WebSurferEvent","source":"WebSurfer","message":"\nThought #1: RECORDED_THOUGHT\nAction #1: executing tool 'left_click' with arguments {\"action\":\"left_click\",\"coordinate\":[100,200]}","action":"left_click","arguments":{"action":"left_click","coordinate":[100,200],"thoughts":"RECORDED_THOUGHT"},"url":"RECORDED_AFTER_URL"}
```

Apply these action mappings:

| Recorded action | WebSurfer action | Required arguments |
|---|---|---|
| `navigate` | `visit_url` | `url` |
| `click` | `left_click` | recorded `[x, y]` coordinate |
| `fill` | `type` | `text`, `delete_existing_text: true`, `press_enter: false` |
| `type` | `type` | `text`, recorded flags when known |
| `press` | `key` | `keys: [recorded key]` |
| `scroll` | `scroll` | `pixels` in Microsoft WebSurfer convention |

Additional rules:

- Round recorded floating coordinates to integer pixels; never relocate the click.
- Coordinates are optional for `type` only when the source did not record them.
- Preserve the actual recorded text and keys.
- Use the recorded action's after-URL for top-level `url`; use the before-URL if no after-URL exists.
- Include `thoughts` in structured `arguments` because `Trajectory` extracts it, but omit `thoughts` from the JSON embedded after `with arguments` in `message`.
- Map Chromium/CDP downward scrolling to negative WebSurfer pixels and upward scrolling to positive pixels. Confirm direction using the thought and before/after scroll state rather than blindly changing the sign.
- Do not add a synthetic termination action unless termination appears in the recorded trajectory.
- Do not drop no-op actions. They remain part of process evidence.

## Phase 3: Prepare the DOM-only dataset

The final DOM task must retain its step evidence and verifier metadata:

```text
dom-data/taskN/
├── actions.json
├── manifest.json
├── trajectory.jsonl
├── agent_browser_decisions.jsonl   # when present
├── agent_browser_final.json        # when present
├── task_data.json
├── final_answer.json
├── web_surfer.log
└── step_XXX/
    ├── action.json
    ├── verifier_action.json
    ├── dom_diff.json
    ├── step.json
    ├── before/
    │   ├── chromiumrl_dom.json
    │   └── page_state.json
    └── after/
        ├── chromiumrl_dom.json
        └── page_state.json
```

Other recorded JSON evidence may remain. Do not delete it merely because the current verifier projection does not consume it.

Copy or generate matching `task_data.json` and `web_surfer.log` files for the paired task. Preserve the same textual final answer, environment-state fields, abort status, and token usage in the DOM `final_answer.json`, but set `screenshots` to `[]` after removing the images. The action history and reported outcome must match across modalities.

Do not copy, synchronize, or modify rubric-related files between the paired task folders. Dataset parity applies only to dataset inputs owned by this skill.

Only after the screenshot dataset passes all checks, remove screenshot image files recursively from that DOM task. Restrict deletion to files whose names identify them as screenshots. Never remove screenshots from `data-screenshot/`.

## Phase 4: Validate before reporting completion

Perform every check:

1. Parse all `.json` files with `jq` or Python JSON parsing.
2. Parse every line of `.jsonl` and `web_surfer.log` independently.
3. Confirm screenshot filenames form `0..N` with no missing number.
4. Confirm all screenshot hashes are unique.
5. Confirm every path in `final_answer.json.screenshots` exists.
6. Confirm `final_answer.json.screenshots` has at least as many action-aligned references as `web_surfer.log` actions, every reference exists, and repeated references correspond to exact duplicates documented in `screenshot_manifest.json`.
7. Confirm web-surfer action count equals the recorded trajectory action count.
8. Confirm action arguments match source evidence.
9. Confirm every retained screenshot belongs to the task and expected site using its source page-state URL plus visible site identity; reject stale cross-task frames.

10. Confirm exactly one lowercase `*_answer.json` exists in each verifier task.
11. Load the screenshot task with Microsoft's parser:

```python
from webeval.trajectory import Trajectory

trajectory = Trajectory.from_folder("data-screenshot/taskN")
assert trajectory is not None
```

12. Confirm the DOM task contains `task_data.json`, `final_answer.json`, and `web_surfer.log`.
13. After screenshot removal, confirm the DOM task contains zero screenshot image files and `final_answer.json.screenshots` is an empty list.
14. Confirm the paired screenshot task still contains all retained images.
15. Confirm every pre-existing rubric-related file still has its original byte hash.
16. Check version-control status only for the two destination task folders; do not stage or commit unless explicitly requested.

## Common mistakes to prevent

- Creating verifier files only under `data-screenshot/` and forgetting them under `dom-data/`.
- Copying all before and after screenshots, producing duplicates and confusing chronology.
- Starting at `step_001/after` and omitting a valid task-aligned initial before-state.
- Retaining `step_001/before` without checking that it belongs to the current task and site.
- Naming images `screenshot_1.png`, leaving gaps, or sorting `screenshot10` before `screenshot2` logically.
- Dropping an action because its screenshot is a duplicate. Deduplicate files, not action-aligned references.
- Supplying fewer screenshot references than actions; Microsoft strict loading fails even when the missing action shares an identical frame.
- Fabricating coordinates even though they exist in `trajectory.jsonl` or `verifier_action.json`.
- Copying `fill`, `press`, `navigate`, or positive CDP scroll values directly without WebSurfer mapping.
- Inventing a successful final answer for a failed run.
- Treating `status: failure` as `is_aborted: true` without evidence of an abort.
- Leaving multiple answer files matching `*_answer.json`.
- Leaving screenshot paths in the DOM `final_answer.json` after deleting the referenced images.
- Deleting step JSON or DOM evidence while removing screenshots.
- Deleting screenshots from the screenshot dataset.
- Creating, editing, synchronizing, or requiring `task_data_with_canonical_rubric.json` during dataset preparation.
- Changing a frozen rubric JSON/TSV or rubric-generation metric while normalizing dataset files.
- Modifying verifier code, generating rubrics, running judges, or committing files without authorization.

## Completion report

Report:

- exact screenshot and DOM task paths;
- source task used;
- action count per task;
- retained screenshot count;
- omitted exact-duplicate count and mapping;
- presence of `task_data.json`, `final_answer.json`, and `web_surfer.log` in both modalities;
- parser and JSON validation results;
- confirmation that DOM screenshots are zero and screenshot-dataset images remain intact;
- confirmation that pre-existing rubric-related artifacts were left byte-for-byte unchanged;
- any non-fabricable evidence that was missing.
