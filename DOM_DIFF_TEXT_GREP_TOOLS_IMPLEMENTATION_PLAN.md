# Raw DOM-Diff Grep/Read-File Verifier — Implementation Plan

Status: **DRAFT — approval required before implementation or paid evaluation.**

This experiment replaces model-facing inline DOM evidence with a verifier-local,
read-only evidence bundle. The judge initially receives the task, frozen rubric,
ordered file manifest, and two tool definitions, but no `dom_diffN.txt` contents.
It must search and read exact source ranges before returning relevance or evidence
analysis judgments.

The evidence-source boundary changes; the benchmark controls and shared verifier
after evidence analysis do not. Microsoft, `dom_diff_summary`, `dom_diff_text`, and
`dom_diff_text_summary` remain unchanged.

## Primary design decisions

| Question | Decision | Evidence / reason |
|---|---|---|
| What is the page-observation source? | Only the immutable, ordered `dom_diff1.txt` … `dom_diffN.txt` files. | No projection, compaction, summary JSON, screenshot, snapshot, or page-state fallback is permitted. |
| Is a raw file uploaded as an API `input_file`? | **No.** “Attachment” means binding a local file to an opaque verifier evidence handle. | OpenAI documents that `.txt` `input_file` items are text-extracted for the model, which would defeat the experiment: [File inputs](https://developers.openai.com/api/docs/guides/file-inputs). |
| How does content enter model context? | Only through the exact output of `grep_evidence` or `read_file`. | In custom function calling, the application executes the requested function and explicitly sends its output back to the model: [Function calling flow](https://developers.openai.com/api/docs/guides/function-calling#how-it-works). |
| Is relevance retained? | Yes: one logical batched relevance session produces the full criterion × FRAME matrix. | Shared top-K selection needs the same matrix contract as the existing verifier. |
| Is analysis retained? | Yes: one logical packed-analysis session handles all criteria after shared top-K. | The initial analysis request contains only selected-file handles and criterion allowlists; raw evidence arrives through tools. |
| What rejoins the shared verifier? | Validated `evidence_by_criterion`. | Reality checking, conditional handling, rescoring, penalties, outcome, failure analysis, validity, denominator, and reporting remain shared. |

## Proposed pipeline

```text
data-new-short-dom/<task-id>/
  task_data.json + final_answer.json + web_surfer.log + dom_diffN.txt
        |
        v
existing DOM-text dataset/frozen-rubric preflight
        |
        v
local read-only RawEvidenceBundle
  FRAME 0 -> opaque file_id -> dom_diff1.txt (host path only)
  FRAME 1 -> opaque file_id -> dom_diff2.txt
  ...
        |
        +---------------- relevance tool session ----------------+
        | initial prompt: task + rubric + manifest + tool schemas |
        | grep/read exact raw ranges; no inline source corpus      |
        +----------------------------------------------------------+
        |
        v
criterion × FRAME relevance matrix
        |
        v
existing shared top-K/grouping
        |
        v
criterion -> allowed FRAME mapping + unique selected-file union
        |
        +---------------- analysis tool session ------------------+
        | initial prompt: controls + allowlists + selected manifest|
        | grep/read exact raw ranges from selected files only      |
        +----------------------------------------------------------+
        |
        v
validated evidence_by_criterion
        |
        v
existing shared reality check -> rescoring -> penalties -> outcome
-> failure analysis -> validity -> score/denominator/reporting
```

One “tool session” is one logical verifier stage but may require several API
model calls: model request, tool call, application tool output, and follow-up
model request. Every call and retry is counted; the extra call topology is not
hidden.

## Exact new files

No existing verifier source file will be edited.

| New file | Responsibility |
|---|---|
| `webeval/src/webeval/rubric_agent/dom_diff_text_grep_tools.py` | Immutable raw-file registry, FRAME/STEP/file-ID manifest, function schemas, safe grep and range-read execution, provenance, pagination, and per-call receipts. |
| `webeval/src/webeval/rubric_agent/dom_diff_text_grep_transport.py` | Isolated Chat Completions/Responses tool-call normalization and transcript handling without changing shared clients. |
| `webeval/src/webeval/rubric_agent/dom_diff_text_grep_prompts.py` | Raw-evidence grounding rules, relevance instructions/schema, and packed-analysis instructions/schema. Contains no DOM evidence. |
| `webeval/src/webeval/rubric_agent/dom_diff_text_grep_agent.py` | New agent subclass; loads raw handles, runs relevance and analysis tool loops, validates outputs, records metrics, and returns shared `evidence_by_criterion`. |
| `webeval/scripts/verify_trajectories_dom_diff_text_grep.py` | Isolated runner, preflight-before-client-init, frozen-rubric enforcement, config identity, score artifacts, call/token metrics, and tool/model traces. |
| `webeval/scripts/diagnose_dom_diff_text_grep.py` | Offline-only payload/leak check, registry/tool diagnostics, source coverage statistics, and fake-client smoke run. |
| `webeval/tests/test_dom_diff_text_grep_tools.py` | Registry, security, grep, range reading, pagination, exact-source and provenance tests. |
| `webeval/tests/test_dom_diff_text_grep_transport.py` | Chat/Responses transcript and tool-call normalization tests. |
| `webeval/tests/test_dom_diff_text_grep_agent.py` | Relevance/analysis loop, validation, retries, coverage, and shared-boundary tests with scripted clients. |
| `webeval/tests/test_dom_diff_text_grep_runner.py` | Preflight, evidence isolation, frozen-rubric, identity, artifact, and no-initial-inline tests. |

Test fixtures will reuse the existing raw `tests/fixtures/dom_diff_text/**/dom_diff1.txt`
files and temporary files created by `tmp_path`; no projected/summary fixture is
an evidence dependency.

## Existing code reused unchanged

| Existing file/function | Reuse |
|---|---|
| `dom_diff_text_adapter.py`: `preflight_dom_diff_text_bundle`, `discover_dom_diff_text_paths`, `validate_frozen_rubric`, `semantic_action_definitions` | Dataset isolation, contiguous action alignment, source-schema validation, semantic log compatibility, and frozen-rubric validation. The parsed frames produced during validation are discarded; they are never used for retrieval or prompts. |
| `dom_diff_adapter.py`: `ordered_action_events` | Stable action count and chronology. |
| `dom_diff_summary_agent.py`: small generic helpers such as `_rubric_text`, `_criteria_block`, `_unknown_analyses` | Response formatting/validation support only. No summary loading, compaction, retrieval, rendering, or capping function is called. |
| `mm_rubric_agent.py`: `_group_screenshots_by_criterion`, `_filter_irrelevant_screenshots`, `_normalize_batched_analysis_response`, `_validate_evidence_analysis`, `_dual_write_evidence_fields`, and `run` downstream stages | Shared top-K, validation primitives, reality check, rescoring, penalty, outcome, failure, validity, denominator, and score behavior. |
| `dom_diff_agent.py`: `_EVIDENCE_STATUSES` | Existing supported/contradicted/partial/unknown vocabulary. |
| `oai_clients/graceful_client.py` and `oai_clients/wrapper.py` | Same configured endpoints, model names, retry policy, and provider usage counters. |

The new runner will copy only the small runner-local loading, call-count, digest,
and report helpers it needs. It will not import another runner or refactor any
existing runner to manufacture reuse.

## Raw file attachment/reference mechanism

### Verifier-local attachment

`RawEvidenceBundle` will be constructed after preflight from the declared,
canonical evidence paths. For each file it stores, on the host only:

```text
task_id
FRAME (zero-based citation identifier)
STEP (one-based action chronology)
opaque file_id, e.g. evidence_frame_0000
canonical path
filename
SHA-256
byte count
line count and byte/line offsets
```

The model-facing manifest contains only:

```text
FRAME 0 | STEP 1 | file_id=evidence_frame_0000 | file=dom_diff1.txt | lines=812
FRAME 1 | STEP 2 | file_id=evidence_frame_0001 | file=dom_diff2.txt | lines=126
```

It contains no header values, URLs, diff records, text nodes, element records,
or source excerpts. Absolute paths are never model-visible. Tool arguments use
only allowlisted opaque IDs; path traversal is impossible by schema and executor.

### Why not an API file upload

The request must contain none of the following:

- an `input_file` item;
- an OpenAI Files API ID;
- Base64 file data;
- a file URL;
- a vector-store/File Search attachment;
- raw file bytes in a text message.

The official file-input behavior extracts non-PDF text into model context. A
literal API `.txt` attachment therefore cannot satisfy “the model does not
receive the whole file.” The approved mechanism must be the local opaque-handle
design above.

### Verification that no implicit injection occurs

Before any paid run, tests and the offline diagnostic will capture the exact
serialized initial relevance and analysis requests and assert:

1. no `input_file`, file-upload ID, file URL, or Base64 payload exists;
2. fixture sentinel text present only in `dom_diffN.txt` is absent;
3. the request contains only manifest metadata and tool schemas;
4. source text first appears only in a recorded tool-result message;
5. no shared transition/projection helper puts source content into a later
   request outside the recorded tool-output lineage.

Because the API receives neither a local path it can access nor uploaded file
contents, it cannot automatically inject the file. This is also checked at the
actual outgoing-payload boundary, not inferred from prompt construction alone.

## Tool schemas

Both tools are read-only and operate on the original UTF-8 source. They never
rewrite, normalize, summarize, or semantically parse evidence.

### `grep_evidence`

```json
{
  "type": "function",
  "function": {
    "name": "grep_evidence",
    "description": "Search exact raw DOM-diff text and return provenance-tagged matching ranges.",
    "strict": true,
    "parameters": {
      "type": "object",
      "properties": {
        "query": {"type": "string", "minLength": 1, "maxLength": 300},
        "file_ids": {"type": "array", "items": {"type": "string"}},
        "mode": {"type": "string", "enum": ["literal", "regex"]},
        "case_sensitive": {"type": "boolean"},
        "context_before": {"type": "integer", "minimum": 0, "maximum": 5},
        "context_after": {"type": "integer", "minimum": 0, "maximum": 5},
        "match_offset": {"type": "integer", "minimum": 0},
        "max_matches": {"type": "integer", "minimum": 1, "maximum": 100}
      },
      "required": ["query", "file_ids", "mode", "case_sensitive", "context_before", "context_after", "match_offset", "max_matches"],
      "additionalProperties": false
    }
  }
}
```

An empty `file_ids` list means all files allowed for that stage. Relevance can
search all frames; analysis can search only the post-top-K selected-frame union.
Literal mode is preferred. Regex mode has a pattern-length guard, execution
timeout, and no shell interpolation.

The result contains exact source excerpts plus:

```text
query/mode
searched file IDs
FRAME, STEP, filename
line_start/line_end and, for an overlong line, column_start/column_end
total matches, returned matches, next match_offset
complete=true/false and an explicit omission/pagination reason
source SHA-256
```

### `read_file`

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read an exact line range from one allowlisted raw DOM-diff file.",
    "strict": true,
    "parameters": {
      "type": "object",
      "properties": {
        "file_id": {"type": "string"},
        "start_line": {"type": "integer", "minimum": 1},
        "end_line": {"type": "integer", "minimum": 1},
        "start_column": {"type": "integer", "minimum": 0}
      },
      "required": ["file_id", "start_line", "end_line", "start_column"],
      "additionalProperties": false
    }
  }
}
```

The executor returns complete requested lines until the configured per-result
limit. If one raw line itself exceeds that limit, it returns an exact UTF-8-safe
column slice with a continuation cursor. It never silently clips or rewrites a
record. The response reports requested vs returned ranges, EOF, continuation,
and source hash.

Starting safety defaults, all configurable and included in run identity:

- 100 grep matches maximum per call;
- 5 context lines on either side;
- 8,000 returned characters per tool call;
- 12 tool rounds and 40 tool calls per stage;
- the existing model context limit as the hard request boundary.

These are transport guards, not evidence-selection claims. Hitting a limit is
always exposed to the model and audit log; the model may issue a narrower or
continued request.

## Model/tool-call loop

Pseudocode for both stages:

```python
messages = initial_messages_without_source_content
for turn in range(config.max_tool_rounds):
    assert_request_within_context(messages, tool_schemas)
    result = await client.create(messages=messages, tools=tool_schemas)
    audit_model_call(request=messages, response=result, usage=result.usage)

    calls = normalize_tool_calls(result)  # Chat Completions or Responses
    if calls:
        append_assistant_tool_call_items(messages, result)
        for call in calls:
            output = execute_allowlisted_tool(call)
            audit_tool_call(call, exact_output=output)
            append_tool_output(messages, call.id, output)
        continue

    parsed = parse_and_validate_stage_json(result.content)
    if parsed.valid:
        return parsed.value
    append_criterion_specific_correction(messages, parsed.errors)

return explicit_stage_failure_or_existing_unknown_fallback()
```

The transport module normalizes the two repository client shapes:

- Chat Completions wrappers already pass `tools` and expose
  `CreateResult.tool_calls`.
- The Responses wrapper accepts `tools`, but its current `CreateResult` does
  not populate `tool_calls`; the isolated transport must read function-call
  items from `CreateResult.message.output` and emit matching
  `function_call_output` items on the next turn.

Before implementation proceeds to a live run, an offline compatibility test
must prove the selected evaluation config exposes a homogeneous, supported
tool-call transport. Unsupported or mixed transports fail preflight rather than
silently falling back to inline evidence. Shared client files remain unchanged.

## Relevance flow

1. Load only raw file handles into `RawEvidenceBundle`.
2. Build a no-content initial prompt containing task, initial URL context,
   frozen rubric criteria, FRAME/STEP manifest, search guidance, and final JSON
   contract.
3. Start one logical batched relevance tool session over all file IDs.
4. Instruct the model to search criterion terms, phrases, exact numbers, dates,
   units, semantic states, navigation/status headers, and coverage/truncation
   warnings; “not found” is not evidence of absence.
5. Require exactly one row per FRAME, in ascending order, with
   `evidence_idx=FRAME` and integer `criterion_N` values in `[0, 10]`.
6. Apply the same completeness/index/range validation as the summary batched
   relevance contract. Invalid output receives a precise correction and retry.
7. Pass the valid matrix into shared
   `MMRubricAgent._group_screenshots_by_criterion`; preserve existing maximum-K
   and irrelevant-frame filtering settings.

The logical stage remains batched, but all API turns required for tool use are
reported separately.

## Analysis flow

1. Start from the shared post-relevance criterion → FRAME groups.
2. Apply the existing configured minimum-relevance filtering behavior.
3. Derive once, from that final set:
   - `criterion_frame_assignments`;
   - the unique selected-FRAME union;
   - the analysis-stage tool allowlist.
4. Render only the compact allowlist and selected-file manifest in the initial
   analysis request. Do not render any DOM records.
5. Run one logical packed-analysis tool session for all criteria.
6. Require the existing analysis fields and `evidence_indices` containing only
   FRAME values from that criterion’s displayed allowlist; STEP remains
   chronology only.
7. Reject invalid/unassigned citations without coercion. Report all invalid
   criterion/frame pairs in one correction when possible.
8. Require every cited FRAME to have appeared in at least one successful
   analysis-stage tool result. Line ranges remain in the audit trace; concise
   `FRAME n, lines x-y` references are encouraged in `evidence_text`.
9. Use shared normalization, evidence validation, dual DOM/screenshot field
   compatibility, and return the normal `evidence_by_criterion` shape.

From `evidence_by_criterion` onward, no tool-specific scoring path exists.
Downstream prompts receive the validated analysis summaries, as they do for
other modalities; they do not receive the raw corpus again.

## Prompt rules

The new prompts will state:

- raw DOM-diff files are authoritative browser-state evidence;
- action history and final answer are context/claims, not page-state proof;
- operation direction and scope are distinct (`added`, `removed`, changed,
  viewport entered/exited);
- search misses are not proof of absence;
- source truncation/coverage warnings require `unknown` when evidence is
  insufficient;
- FRAME is the only citation index; STEP is chronology;
- the model must inspect evidence with tools before judging;
- output must use the existing relevance or analysis JSON schema.

No compact `+DOC/-DOC` renderer, summary receipt, chunk ID, `C[...]` tag,
criterion chunk retrieval, deterministic lexical fallback, S3 cap, or inline
evidence block is imported into this path.

## Token and call accounting

The runner will retain existing provider usage counters and add a stage-level
ledger. Every API attempt records:

```text
stage/session/turn/validation_attempt
model and endpoint family
request SHA-256 and exact serialized request artifact
tool-schema estimated tokens
prompt/input tokens (actual provider usage)
completion/output tokens
reasoning tokens
finish reason
logical call number, API attempt number, retry reason
raw response and tool-call arguments
```

Every tool execution records:

```text
call_id, tool, validated arguments
exact returned payload
FRAME/STEP/file/line/column provenance
result characters and estimated tokens
complete/paginated/error status
source SHA-256 at registration and read time
```

Per stage and per run, report:

- raw source bytes and estimated raw tokens (offline denominator only);
- unique source ranges and tokens returned;
- cumulative tool-output tokens sent;
- overlap/re-read tokens;
- actual prompt, completion, reasoning, and total verifier tokens;
- logical model calls, API attempts, retries, tool rounds, and tool calls;
- files/frames/lines touched and untouched;
- relevance/analysis validation attempts;
- context-limit and pagination events;
- final relevance matrix, top-K groups, and criterion assignments.

Actual provider usage is authoritative. Raw file size/tokens are not counted as
model input because the files are not sent. Repeated conversation history in
later tool rounds is counted each time the provider reports it; this prevents
the experiment from hiding tool-loop overhead.

Artifacts per run:

```text
scores/mmrubric-dom-diff-text-grep-<identity>.json
scores/mmrubric-dom-diff-text-grep-<identity>.model_calls.jsonl
scores/mmrubric-dom-diff-text-grep-<identity>.tool_calls.jsonl
```

The cache/run identity includes source hashes, frozen-rubric hash, model/config,
tool schemas, retrieval limits, prompt version, and verifier schema version.

## Failure and coverage behavior

| Condition | Behavior |
|---|---|
| Noncontiguous/misaligned files, forbidden evidence, missing frozen rubric | Fail preflight before client creation. |
| Source hash changes after registration | Abort the task; never mix versions. |
| Unknown file ID/path traversal | Return a structured tool error and log it; no filesystem access. |
| Invalid or unsafe regex | Return a structured error; allow a corrected literal/narrow regex call. |
| Result limit reached | Return a continuation/omission receipt; never imply complete coverage. |
| Context would overflow | Do not silently truncate history or source output. Record the limit and end the stage through the explicit existing failure/unknown behavior. |
| Invalid relevance matrix | Correction retry; after configured attempts, use the existing zero-matrix failure behavior and mark the stage degraded. |
| Invalid analysis or FRAME citation | Criterion-specific correction retry; after configured attempts, use existing `unknown` analyses and mark the stage degraded. |
| Tool-round/call limit reached | Same explicit degraded-stage behavior; preserve the complete trace. |
| Source coverage warning found | Make it model-visible through the tool result; require `unknown` when it prevents a grounded conclusion. |
| No match found | Never interpret as proof of absence. |

The score artifact must surface `retrieval_degraded`, failure reason, untouched
frames, and incomplete tool pages so a numerically produced score cannot be
mistaken for a fully covered run.

## Tests before any paid evaluation

### Unit tests

- canonical FRAME/STEP/file-ID mapping and numeric `dom_diffN.txt` order;
- immutable SHA and change-during-run detection;
- literal/regex/case/context behavior;
- multi-file search and analysis-stage allowlist restriction;
- line and column provenance;
- whole-line reads, overlong-line continuation, grep pagination;
- no path arguments, traversal, symlink escape, or forbidden-file access;
- exact source bytes returned with no normalization/projection;
- Chat Completions and Responses tool-call transcript normalization;
- actual tool schema token counting.

### Agent tests with scripted clients

- relevance: grep → read → valid full matrix succeeds;
- relevance invalid schema/index/score receives a useful retry;
- shared top-K receives the returned matrix unchanged;
- analysis receives the exact final criterion allowlist and selected union;
- valid multi-criterion analysis succeeds first validation attempt;
- unassigned, STEP-valued, nonexistent, or never-retrieved FRAME citations fail;
- several bad criterion citations are reported together;
- pagination/context/round exhaustion produces explicit degraded receipts;
- shared `evidence_by_criterion` shape is unchanged.

### Isolation and payload tests

- initial relevance/analysis serialized requests contain unique raw sentinels
  zero times;
- no `input_file`, Files API ID, Base64, URL attachment, screenshot, summary,
  snapshot, page-state, or old DOM path appears;
- sentinel first appears only in the corresponding tool result;
- later request occurrences are traceable to prior tool outputs;
- the validation-only parsed frame is never passed to the agent/tool registry;
- downstream global transition input contains no raw corpus projection.

### Regression tests

- existing Microsoft/screenshot tests unchanged;
- existing `dom_diff_summary` tests unchanged;
- existing `dom_diff_text` tests unchanged;
- existing `dom_diff_text_summary` tests unchanged;
- shared `MMRubricAgent` tests unchanged.

### Offline acceptance gate

Run the diagnostic with a fake client against representative small and large
tasks. Review the exact initial payload, tool outputs, coverage report, call
waterfall, and final shared-boundary object. No live judge call is allowed until
these assertions and all focused/regression tests pass.

## Controlled benchmark plan

After explicit approval for paid calls:

1. Select paired tasks with already frozen rubrics, including short and large
   DOM trajectories.
2. Verify task ID, rubric object/hash, denominator, semantic trajectory, final
   answer, model names, endpoint configuration, scoring settings, and validity
   settings before either run.
3. Run the unchanged Microsoft screenshot baseline and the new raw-tool variant.
4. Also compare against existing saved `dom_diff_text_summary` results where
   provenance matches; do not rerun or modify that verifier merely for reuse.
5. Report criterion score, normalized score, outcome, validity, agreement,
   prompt/completion/reasoning/total tokens, calls/retries, unique evidence
   retrieved, retrieval ratio, untouched frames, and degraded coverage.
6. Attribute token differences by relevance, analysis, rescoring, outcome,
   failure analysis, and validity/other.

Success is not “fewer initial prompt tokens” alone. The variant must reduce
total actual verifier tokens while preserving score/evidence fidelity and must
not achieve savings by silently missing relevant evidence.

## Implementation order after approval

1. Add raw registry and two tool executors with security/provenance tests.
2. Add transport normalization with fake Chat/Responses tests.
3. Add no-content prompts and payload-leak diagnostic.
4. Add relevance tool session and matrix validation.
5. Connect unchanged shared top-K.
6. Add analysis tool session, final criterion allowlists, and citation checks.
7. Connect `evidence_by_criterion` to unchanged downstream scoring.
8. Add isolated runner, identity, token/call ledger, and trace artifacts.
9. Run focused tests, all unchanged regressions, and offline representative
   diagnostics.
10. Stop for artifact review and separate approval before any paid evaluation.

## Approval points / unresolved risks

- Approve the verifier-local meaning of “file attachment.” A literal OpenAI
  `input_file` upload is incompatible with the no-auto-injection requirement.
- Confirm the selected benchmark endpoint supports the isolated tool transport;
  otherwise implementation stops rather than switching models/endpoints.
- Tool use may save corpus tokens but add repeated conversation/tool-round
  tokens. The instrumentation deliberately measures both unique retrieval and
  cumulative billed prompt usage.
- Grep-driven discovery can miss paraphrases or relational evidence. Coverage
  receipts and score parity tests are mandatory; no deterministic parser-derived
  facts may be injected to compensate.
- A model can choose overly broad reads. Per-call pagination prevents one call
  from silently dumping the corpus, but limits are disclosed and configurable.

No implementation, dataset mutation, rubric generation, or judge evaluation is
authorized by this plan.
