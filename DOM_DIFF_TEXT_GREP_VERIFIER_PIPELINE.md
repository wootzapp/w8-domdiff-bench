# Raw DOM-Diff Grep/Read Verifier: End-to-End Pipeline

The `dom_diff_text_grep` verifier is an isolated evidence-delivery variant of the shared Universal Verifier. It reads only action-aligned raw `dom_diffN.txt` files, exposes them through two read-only tools, produces the same criterion-by-frame relevance matrix and criterion evidence shape expected by `MMRubricAgent`, and then uses the existing downstream reality checking, rescoring, penalty, outcome, failure, validity, denominator, and reporting logic.

The raw files are not uploaded or pasted into the initial model request. The verifier registers them locally behind opaque IDs, sends only a metadata manifest and tool schemas, and appends exact source excerpts to the conversation only after the model calls `grep_evidence` or `read_file`. Existing screenshot, `dom_diff_summary`, `dom_diff_text`, and `dom_diff_text_summary` implementations are outside this variant and remain separate.

| Component or stage | Role | Evidence or current behavior | How to verify | Files or controls |
|---|---|---|---|---|
| Dataset preflight | Proves the task is an isolated, action-aligned raw-text bundle with a frozen rubric | Requires one contiguous `dom_diff1.txt…dom_diffN.txt` per action; rejects screenshots and alternate DOM/page-state evidence | Run the runner preflight or offline diagnostic | `dom_diff_text_adapter.py`, `verify_trajectories_dom_diff_text_grep.py` |
| Local evidence registry | Maps `FRAME 0…N-1` and `STEP 1…N` to immutable raw files | Stores canonical path, opaque ID, SHA-256, bytes, and line count locally; only manifest metadata is model-visible | Inspect source metadata in the score receipt | `dom_diff_text_grep_tools.py: RawEvidenceBundle` |
| Tool transport | Carries function calls and outputs across supported endpoint styles | Supports homogeneous Chat Completions or Responses-style endpoints; no Files API path | Transport tests and `validate_tool_transport()` | `dom_diff_text_grep_transport.py`, runner |
| Relevance tool session | Lets GPT-5.2 search raw evidence and return the full criterion × FRAME matrix | Starts with no raw DOM content; tools may search all frames; output has one zero-based row per FRAME | Model/tool JSONL traces and relevance validator | `dom_diff_text_grep_agent.py`, `dom_diff_text_grep_prompts.py` |
| Shared top-K | Selects relevant frames per criterion from the relevance matrix | Uses unchanged `MMRubricAgent._group_screenshots_by_criterion()` and optional irrelevant-frame filtering | Inspect `relevance_matrix`, `selected_frame_union`, and assignments in score JSON | `mm_rubric_agent.py` |
| Analysis tool session | Retrieves evidence from only the selected-frame union and produces criterion analyses | Prompt displays exact criterion→allowed-FRAME lists; citations must also have been retrieved during analysis | Analysis trace, coverage receipt, and validation failures | `dom_diff_text_grep_agent.py`, prompts, tools |
| Shared downstream verifier | Converts validated evidence into rubric and outcome results | Reality check, conditional handling, rescoring, penalties, outcome, first failure, and validity are inherited | Compare call path in `_generate_reply()` | `mm_rubric_agent.py` |
| Runner and receipts | Enforces configuration identity and saves scores, token/call metrics, and complete traces | Writes one score JSON plus separate model-call and tool-call JSONL artifacts | Inspect a completed run directory | `verify_trajectories_dom_diff_text_grep.py` |
| Offline diagnostic | Checks file discovery, zero-DOM initial payload, and basic grep/read behavior without judge calls | Uses a local token counter and performs deterministic smoke calls | Run `diagnose_dom_diff_text_grep.py` | Diagnostic script |

## 1. Pipeline at a glance

```text
data-new-short-dom/<task-id>/
  task_data.json
  final_answer.json
  web_surfer.log
  dom_diff1.txt ... dom_diffN.txt
        |
        v
existing strict DOM-text preflight
  - frozen rubric required
  - action/diff count and URL/type alignment
  - forbidden evidence rejected
  - parsed frames used only for validation, then discarded
        |
        v
NEW RawEvidenceBundle
  FRAME 0 | STEP 1 -> evidence_frame_0000 -> dom_diff1.txt
  FRAME 1 | STEP 2 -> evidence_frame_0001 -> dom_diff2.txt
  ...
        |
        v
NEW relevance tool session
  initial prompt: task + rubric + metadata-only manifest + tool schemas
  model loop: grep/read -> exact tool output -> follow-up request
  output: complete criterion × FRAME relevance matrix
        |
        v
EXISTING shared top-K and irrelevant-frame filtering
  output: criterion -> selected FRAME list
        |
        v
NEW analysis tool session
  initial prompt: action history + final answer + selected manifest
                  + criterion -> allowed FRAME mapping
  model loop: grep/read selected files -> exact tool output -> analysis JSON
  output: validated evidence_by_criterion
        |
        v
EXISTING shared MMRubricAgent downstream pipeline
  conditional handling -> reality check -> rescoring -> penalties
  -> outcome -> first-point-of-failure -> validity -> score/report
```

The format-specific boundary ends when `_analyze_dom_evidence_batched()` returns validated `evidence_by_criterion`. Everything after that is the shared `MMRubricAgent` pipeline.

## 2. Input and dataset contract

The runtime task directory must contain:

```text
<task-id>/
├── task_data.json
├── final_answer.json
├── web_surfer.log
├── dom_diff1.txt
├── dom_diff2.txt
└── ... dom_diffN.txt
```

The known provenance sidecar `task_data_with_canonical_rubric.json` is allowed, but it is not an implicit scoring fallback. The runtime `task_data.json` itself must contain the frozen `precomputed_rubric`.

### Preflight checks

`preflight_trajectory()` calls `preflight_dom_diff_text_bundle(..., require_frozen_rubric=True)` before model clients are initialized. The reused preflight validates:

- exactly one canonical task in `task_data.json`;
- exactly `web_surfer.log`, not an alternative log name;
- exactly one `final_answer.json`;
- no `screenshots` key in the DOM final answer;
- `final_answer.json.token_usage == {}`;
- a non-empty, unscored frozen rubric with positive `max_points`;
- a frozen-rubric SHA-256 and fixed denominator;
- no screenshots, `dom_diff.json`, summary JSON, snapshots, page-state JSON, verifier-action JSON, or agent-browser observation files;
- numeric and contiguous `dom_diff1.txt…dom_diffN.txt` discovery;
- one diff per WebSurfer action;
- normalized action-type and after-URL alignment;
- cleared legacy/alternate DOM evidence fields in the shared input object.

The strict parser loads the text files during preflight to validate their schema and action alignment. The grep runner then explicitly discards those parsed frames with `del parsed_frames`; the parser output is not used as model evidence.

`validate_raw_tool_file_contract()` adds a second boundary check: every registered file must be the exact root-level `dom_diffN.txt` under that runtime task directory, ordered as:

```text
dom_diff1.txt -> FRAME 0 -> STEP 1
dom_diff2.txt -> FRAME 1 -> STEP 2
...
dom_diffN.txt -> FRAME N-1 -> STEP N
```

An identically named file outside the task root is rejected.

## 3. RawEvidenceBundle and immutable source handling

`RawEvidenceBundle.from_dom_actions()` creates one `RawDOMDiffFile` for each action. It records locally:

```text
task_id
frame_index          # zero-based citation ID
action_ordinal       # one-based chronology
action_id
file_id              # opaque, e.g. evidence_frame_0000
canonical path       # never shown to the model
filename
source SHA-256
source byte count
line count
```

Registration enforces UTF-8, canonical `dom_diffN.txt` naming, contiguous FRAME/STEP mapping, and no symlink escape. Every subsequent tool read recalculates the SHA-256; if a source changes after registration, the call fails instead of reading mutated evidence.

The bundle exposes `RawDOMDiffFrame` metadata objects to the shared verifier. Their `diff` fields are deliberately empty. This prevents the shared DOM transition projector from reconstructing or injecting a raw corpus outside the grep/read path.

### Model-facing manifest

The initial model sees only metadata such as:

```text
FRAME 0 | STEP 1 | file_id=evidence_frame_0000 | file=dom_diff1.txt | lines=410
FRAME 1 | STEP 2 | file_id=evidence_frame_0001 | file=dom_diff2.txt | lines=486
```

It does not see source URLs, DOM records, text nodes, element changes, raw paths, hashes, or file contents until a tool returns them.

## 4. There is no API file upload

“Attachment” in this verifier means a local association between an opaque `file_id` and a canonical task file. The API request contains no:

- `input_file` item;
- OpenAI Files API identifier;
- Base64 file content;
- `file_url`;
- vector-store or file-search attachment;
- readable host filesystem path.

`assert_no_raw_evidence_in_initial_payload()` rejects upload markers, canonical paths, and test sentinels. Both relevance and analysis call this guard when constructing their initial requests. Tests deep-copy and inspect the request at send time to prove source text first appears only in a tool-result message.

## 5. Evidence tools

Both tools are strict function schemas with `additionalProperties: false`.

### `grep_evidence`

Purpose: search exact raw text and return matching source ranges with provenance.

| Argument | Contract |
|---|---|
| `query` | Required string, 1–300 characters |
| `file_ids` | Opaque allowlisted IDs; empty means all files allowed for that stage |
| `mode` | `literal` or `regex` |
| `case_sensitive` | Boolean |
| `context_before`, `context_after` | 0–5 lines each |
| `match_offset` | Non-negative pagination offset |
| `max_matches` | 1–100, additionally bounded by runner configuration |

Literal search is performed in-process, line by line. Regex search invokes `rg` without shell interpolation, under a configurable timeout. The result includes:

- query and search mode;
- searched opaque IDs and source hashes;
- total and returned match counts;
- FRAME, STEP, filename, matched line, source line range;
- exact text excerpt;
- next match offset;
- `complete` and an explicit omission reason.

The default tool-output allowance is 8,000 characters. If a normal result set does not fit, whole matches are paginated. If the first matching raw line itself exceeds the allowance, the tool returns an explicit column range and marks whether that excerpt is complete; the source file remains untouched.

### `read_file`

Purpose: read an exact line range from one stage-allowlisted raw file.

| Argument | Contract |
|---|---|
| `file_id` | One opaque ID allowed in the current stage |
| `start_line` | One-based line number |
| `end_line` | One-based inclusive end line |
| `start_column` | Zero-based column used for continuation |

The result returns exact line/column segments until the per-result character allowance is reached. If it stops mid-line, it returns deterministic continuation coordinates. It also reports EOF, completeness, omission reason, FRAME, STEP, filename, and source hash.

### Stage allowlists

- Relevance executor: every registered raw frame is searchable.
- Analysis executor: only the unique post-top-K selected-frame union is searchable.
- Paths supplied by the model are never accepted; only opaque IDs are valid.

## 6. Model/tool-call loop

Both relevance and analysis use `_run_tool_session()`:

```python
messages = initial_prompt_without_raw_dom
executor = stage_scoped_read_only_executor

for turn in range(max_tool_rounds):
    estimate request tokens including accumulated history and tool schemas
    fail/degrade if request is at or above model context limit

    response = GPT_5_2(messages, tools=[grep_evidence, read_file])
    record exact request, response, finish reason, and provider usage

    if response contains tool calls:
        normalize Chat/Responses tool-call format
        execute only allowlisted tools
        append exact JSON tool outputs to messages
        record arguments, output, characters, and estimated output tokens
        continue

    validate the complete stage JSON
    if valid:
        return stage result

    append one correction containing the validation error
    continue without remapping citations

fail/degrade if round or tool-call limits are exhausted
```

Default controls are configurable and part of run identity:

| Control | Default | Scope |
|---|---:|---|
| Returned characters | 8,000 | Per tool call |
| Grep matches | 100 | Per tool call |
| Tool/model rounds | 12 | Per relevance or analysis stage |
| Evidence tool calls | 40 | Per relevance or analysis stage |
| Regex timeout | 2 seconds | Per regex execution |
| API retries | 2 | Per provider client |
| Request timeout | 180 seconds | Per provider call |

Every earlier tool result remains in the conversation transcript. Consequently, the model receives prior results again on later tool-loop turns. This is auditable but can make cumulative prompt usage much larger than the amount of unique raw evidence retrieved.

## 7. Relevance stage

### Initial request

`build_relevance_initial_messages()` renders:

- task definition and starting-URL context;
- metadata-only manifest for all frames;
- every frozen rubric criterion and description;
- raw-DOM grounding rules;
- the two function schemas.

It does not include raw DOM text, action history, or the final answer.

### Required output

The model must return:

```json
{
  "frames": [
    {
      "evidence_idx": 0,
      "criterion_0": 8,
      "criterion_1": 2
    },
    {
      "evidence_idx": 1,
      "criterion_0": 3,
      "criterion_1": 9
    }
  ]
}
```

`_validate_relevance_response()` requires:

- at least one successful tool result that returned a source range;
- exactly one row for every FRAME;
- ascending zero-based `evidence_idx` values matching their positions;
- one integer score in `[0,10]` for every criterion.

It does not require the model to have retrieved every frame individually before scoring the full matrix. This is a current coverage boundary: all rows are required, but the minimum enforced retrieval proof is at least one returned source range in the relevance session.

If the relevance session fails or exhausts its limits, the agent records degraded retrieval and returns an all-zero matrix rather than changing the shared call topology.

## 8. Shared top-K and criterion assignments

The validated relevance matrix rejoins unchanged shared code:

1. `MMRubricAgent._group_screenshots_by_criterion()` ranks frames by each criterion score.
2. It keeps up to `max_images_per_criterion` frames, default 5.
3. With `ignore_irrelevant_screenshots=True`, `_filter_irrelevant_screenshots()` may remove clearly low-scoring pairs when higher-scoring evidence exists.
4. The grep agent receives `grouped_frames` and converts it into `criterion_frame_assignments`.
5. If a positive inherited `min_relevance_threshold` is configured, only scores strictly greater than that threshold survive. The current inherited default is 0.
6. The unique union of all assigned frames becomes the analysis file allowlist.

These assignments are stored once and feed both the displayed `ALLOWED FRAMES` block and analysis validation:

```text
ALLOWED FRAMES
C0=[0, 2]
C1=[1, 3]
C2=[3]
```

STEP values remain chronology only and are never valid evidence citations.

## 9. Analysis stage

### Initial request

`build_analysis_initial_messages()` contains:

- task and starting-URL context;
- action history as context, not page-state proof;
- agent final answer as a claim, not evidence;
- metadata-only manifest for the selected-frame union;
- the exact criterion→allowed-FRAME mapping;
- all criteria and output-field requirements;
- grounding rules and the two tool schemas.

No raw DOM content is initially inlined. The analysis executor can read only selected files.

### Required output

The model returns one entry per criterion:

```json
{
  "analyses": [
    {
      "criterion_idx": 0,
      "evidence_status": "supported",
      "evidence_text": "FRAME 0 lines 7-10 show ...",
      "criterion_analysis": "...",
      "discrepancies": "None explicitly shown",
      "environment_issues_confirmed": false,
      "evidence_indices": [0]
    }
  ]
}
```

Conditional criteria must also include `condition_verification`.

### Validation

`_validate_analysis_response()` validates every returned criterion before raising, so one correction can report multiple errors. It requires:

- exactly one ordered result per rubric criterion;
- the correct `criterion_idx`;
- `evidence_status` in `supported`, `contradicted`, `partial`, or `unknown`;
- complete shared evidence-analysis fields;
- integer zero-based FRAME citations;
- citations that are a subset of that criterion's displayed assignment;
- citations whose source was actually returned by a successful analysis-stage tool call.

Invalid FRAME values are rejected. They are never converted from STEP numbers or silently remapped. The correction includes the exact validation error and asks for a complete corrected JSON response.

After validation, the agent writes the evidence fields expected by shared code, including `evidence_idx`, `screenshot_idx` as a compatibility alias, `evidence_indices`, and corresponding one-based `steps`.

If analysis fails, the agent emits criterion-level `unknown` results and marks retrieval as degraded.

## 10. Shared downstream verifier

Once `evidence_by_criterion` is returned, the new evidence-delivery path is finished. The inherited `_generate_reply()` continues with:

1. conditional-criterion disambiguation when required;
2. rubric reality checking;
3. evidence-aware rubric rescoring;
4. penalty detection and application;
5. majority-vote selection;
6. outcome verification;
7. first-point-of-failure analysis using semantic action definitions;
8. trajectory-informed validity/ambiguity classification;
9. task-only validity classification;
10. fixed-denominator score and final result assembly.

The runner uses the same GPT-5.2 judge client and o4-mini action/validity client configuration as the controlled baseline. A valid frozen rubric is passed through `precomputed_rubric`, so rubric generation is skipped.

The process pass threshold defaults to 0.8. The top-level binary `score` follows `--success`:

- `process`: process/rubric pass;
- `outcome`: outcome pass, the runner default;
- `both`: process and outcome must both pass.

The score artifact still records earned points, denominator, normalized rubric score, and outcome separately, so a binary score of 0 does not hide the criterion score.

## 11. Token and call accounting

The runner snapshots each client's counters immediately before and after one trajectory and records deltas for:

- prompt tokens;
- completion tokens;
- reasoning tokens;
- total tokens, defined as prompt plus completion because reasoning is already included in completion;
- logical model calls;
- underlying API attempts;
- API retries, calculated as attempts minus logical calls.

The grep agent additionally records every relevance and analysis model call with:

```text
stage
turn
estimated request tokens
deep-copied request messages
tool schemas
response content and finish reason
provider-reported usage
```

Every tool call records:

```text
stage and turn
call ID
tool name
exact arguments
exact structured output
serialized result characters
estimated result tokens (characters // 4)
```

Coverage receipts record allowed file IDs, frames returned, and exact line/column ranges. Unique evidence tokens and overlap/re-read tokens are not stored as first-class score fields; they can be deterministically derived from the exact tool-call JSONL trace.

## 12. Output artifacts

For each trajectory, the runner writes:

```text
<task-dir>/scores/
├── mmrubric-dom-diff-text-grep-<identity>.json
├── mmrubric-dom-diff-text-grep-<identity>.model_calls.jsonl
└── mmrubric-dom-diff-text-grep-<identity>.tool_calls.jsonl

<report-path>.jsonl
```

The score JSON includes:

- evidence, prompt, and verifier schema versions;
- raw source and frozen-rubric hashes;
- frozen and final denominators;
- provider token totals;
- logical calls, API attempts, and retries;
- source-file audit metadata;
- relevance matrix;
- criterion-frame assignments and selected-frame union;
- relevance/analysis rounds, validation failures, coverage, and context events;
- degraded-retrieval status and reasons;
- rubric items, process score, outcome, and top-level score;
- paths to the full model and tool traces.

The run identity hashes models, scoring settings, tool limits, tool schemas, frozen rubric, and raw source files. A different evidence file or configuration produces a different score filename.

## 13. File map

### Grep/read-specific implementation

| File | Responsibility |
|---|---|
| `webeval/scripts/verify_trajectories_dom_diff_text_grep.py` | CLI runner, preflight-before-client-init, exact task-root file contract, client construction, frozen/source/config identity, token/call deltas, score and trace artifacts |
| `webeval/scripts/diagnose_dom_diff_text_grep.py` | Offline registry construction, zero-DOM initial-payload assertion, literal grep/read smoke test, manifest and coverage report |
| `webeval/src/webeval/rubric_agent/dom_diff_text_grep_tools.py` | Opaque raw-file registry, SHA verification, strict tool schemas, literal/regex search, range reading, pagination, stage allowlists, provenance, coverage, initial-payload leak guard |
| `webeval/src/webeval/rubric_agent/dom_diff_text_grep_transport.py` | Chat/Responses tool-call normalization, transcript insertion, token estimation, context-limit lookup |
| `webeval/src/webeval/rubric_agent/dom_diff_text_grep_prompts.py` | Metadata-only relevance and analysis prompts, grounding rules, FRAME/STEP rules, response schemas |
| `webeval/src/webeval/rubric_agent/dom_diff_text_grep_agent.py` | Agent subclass, raw bundle loading, relevance and analysis tool loops, assignments, validators, degradation, runtime metrics, shared evidence projection |

### Existing files reused unchanged

| File | Reused responsibility |
|---|---|
| `webeval/src/webeval/rubric_agent/dom_diff_text_adapter.py` | Numeric diff discovery, strict text parsing for validation only, action alignment, forbidden-evidence isolation, final-answer checks, frozen-rubric hash/denominator, semantic action schema |
| `webeval/src/webeval/rubric_agent/dom_diff_adapter.py` | Ordered action chronology/count |
| `webeval/src/webeval/rubric_agent/mm_rubric_agent.py` | Main execution sequence, shared top-K/filtering, analysis normalization helpers, conditional handling, reality check, rescoring, penalties, outcome, failure, validity, denominator |
| `webeval/src/webeval/oai_clients/graceful_client.py` | Endpoint loading, configured retry behavior, provider selection and usage accumulation |
| `webeval/src/webeval/oai_clients/wrapper.py` | Client capability model, context/token estimates, provider usage counters |
| `webeval/src/webeval/oai_clients/messages.py` | Shared request/result message structures |

### Tests

| File | Covered behavior |
|---|---|
| `webeval/tests/test_dom_diff_text_grep_tools.py` | Metadata-only manifest, no raw sentinel, literal search/provenance, regex pagination, analysis allowlist, read continuation, mutation detection, path/symlink rejection, strict schemas |
| `webeval/tests/test_dom_diff_text_grep_transport.py` | Chat and Responses tool-call normalization and transcript construction |
| `webeval/tests/test_dom_diff_text_grep_agent.py` | Fake relevance→shared top-K→analysis flow, first-attempt success, raw-content isolation, assignment rendering, rejected response logging, combined citation errors, retrieved-frame enforcement |
| `webeval/tests/test_dom_diff_text_grep_runner.py` | Frozen preflight, parsed-projection discard, exact numeric root files, outside-root rejection, isolation from old compaction/retrieval modules, separate trace artifacts, no file-upload path |

## 14. Offline diagnostic and execution

Offline diagnostic, with no judge calls:

```bash
PYTHONPATH=webeval/src python \
  webeval/scripts/diagnose_dom_diff_text_grep.py \
  --input /absolute/path/to/<task-id> \
  --output /absolute/path/to/diagnostic.json
```

Controlled verifier invocation:

```bash
PYTHONPATH=webeval/src python \
  webeval/scripts/verify_trajectories_dom_diff_text_grep.py \
  --input /absolute/path/to/<task-id> \
  --eval-config /absolute/path/to/endpoint_configs/openai/canonical \
  --judge-model gpt-5.2 \
  --o4mini-model o4-mini \
  --rubric-threshold 0.8 \
  --success outcome \
  --max-evidence-per-criterion 5 \
  --majority-vote-instances 1 \
  --request-timeout-seconds 180 \
  --max-api-retries 2 \
  --grep-max-result-chars 8000 \
  --grep-max-matches 100 \
  --grep-max-tool-rounds 12 \
  --grep-max-tool-calls 40 \
  --grep-regex-timeout-seconds 2 \
  --redo-eval \
  --report /absolute/path/to/verify_report.jsonl
```

## 15. Verified facts, inferences, and current boundaries

### Directly verified from code and artifacts

- Only `dom_diffN.txt` paths registered from `dom_actions` can be read by the tools.
- No old DOM compaction, summary projection, S3 capping, or lexical chunk retrieval module is imported by the grep agent.
- Initial relevance and analysis messages contain manifests and tool schemas, not raw file contents.
- Relevance produces the full shared matrix contract; top-K is inherited.
- Analysis displays and validates against the same criterion-frame assignment object.
- Full model/tool transcripts and provider token totals are saved separately.
- The completed Task6 run saved 11 grep-stage model calls and 24 tool calls with exact arguments and outputs under `outputs/dom_diff_text_grep/task6_controlled_20260820T091018Z/`.

### Inferences supported by receipts

- Tool-based retrieval can inspect a small unique fraction of the raw corpus while still consuming high total prompt tokens because every follow-up request replays prior tool outputs and metadata.
- Grep hits on verbose recorder metadata can be much less information-dense than projected summary records, even when the query itself is criterion-relevant.

### Current boundaries and risks

- Relevance validation requires at least one retrieved source range, not proof that every frame was inspected.
- A grep miss is explicitly not treated as proof of absence; coverage quality depends on model search choices.
- Tool output uses a character guard rather than a semantic-record boundary because the input is deliberately raw text. Partial overlong lines are provenance-tagged and continuable.
- The context check fails/degrades rather than silently dropping accumulated history, but history replay itself can dominate token use.
- On relevance-stage failure, the fallback matrix is all zeros; on analysis failure, criterion evidence becomes `unknown`. Both paths are marked degraded in metrics.
- This documentation pass inspected code and completed run artifacts but did not rerun the test suite or a paid evaluation.

## Conclusion

The grep/read variant changes only how raw DOM evidence reaches relevance and analysis: local opaque handles replace inline evidence, and exact tool outputs supply grounded ranges. Its strongest controls are source isolation, immutable hashes, FRAME/STEP separation, selected-frame allowlists, exact citation validation, and complete call traces. Its dominant remaining efficiency risk is cumulative transcript replay across multi-turn tool sessions; the next concrete diagnostic is to compare unique retrieved evidence tokens against cumulative provider prompt tokens per relevance and analysis turn.
