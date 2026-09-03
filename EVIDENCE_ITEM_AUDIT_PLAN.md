# Evidence-Item Error Audit Plan

This audit benchmarks the exact information required by each rubric criterion, such as a publisher name, selected destination, date, control state, or confirmation message. For every evidence item, it records whether the information exists in the screenshot source and DOM-model source, whether each existing verifier recovered it correctly, and which representation performed better.

The audit remains completely offline and outside both verifier packages. Microsoft and DOM verifier prompts, relevance, top-K selection, model calls, evidence analysis, scoring, retries, outcome, validity, and reporting remain unchanged; the audit reads their completed outputs and the corresponding source files only.

## Scope and invariants

| Component | Role | Evidence recorded | Verification | Boundary |
|---|---|---|---|---|
| Screenshot source | Pixel evidence available to Microsoft’s verifier | Exact screenshot filename, visible text/state, and reviewer note | Human inspection | Read-only |
| Screenshot verifier output | What the existing verifier recovered or used | Verbatim evidence analysis and scoring excerpts | Existing `result.json` | No new call or prompt |
| DOM-model source | Structured evidence available to the DOM verifier | Exact `dom_modelN.txt`, line range, quoted value/state | Exact text/line check | Read-only |
| DOM verifier output | What the existing verifier recovered or used | Verbatim evidence analysis and scoring excerpts | Existing `result.json` | No new call or prompt |
| Evidence-item audit | Compares source availability with verifier recovery | Presence, caught/missed, classification, advantage | Manual source review plus deterministic validation | Cannot affect verifier results |

Hard requirements:

- Work only inside `evidence-error-experiment/`.
- Do not modify `benchmarks-2/`, `benchmarks/`, or `ms-paper-execution/`.
- Do not modify either copied verifier package.
- Do not add LLM calls, prompts, agents, observers, or scoring stages.
- Preserve existing verifier evidence strings verbatim.
- Use one frozen rubric/hash and matching criterion order.
- Keep manual decisions in audit sidecars, never source datasets or verifier artifacts.
- Record absent evidence separately from verifier misses.

## Unit of audit

The unit is one concrete **evidence item** within a rubric criterion. This is intentionally lightweight: the reviewer writes a short evidence requirement and expected value, rather than creating a new rubric or model-generated decomposition.

Example:

```text
Criterion: Report publisher, developer, and release date

E1: Publisher = Electronic Arts
E2: Developer = Tiburon
E3: Release date = 8/13/2026
```

Each evidence item records:

```json
{
  "criterion_index": 2,
  "evidence_id": "C2-E1",
  "evidence_requirement": "Publisher shown on the product page",
  "expected_value": "Electronic Arts",
  "screenshot": {
    "source_present": true,
    "source_citations": [
      {
        "file": "screenshot6.png",
        "visible_text": "Published by Electronic Arts",
        "locator": "metadata row above Compare editions"
      }
    ],
    "verifier_caught": true,
    "verifier_evidence_excerpt": "Published by Electronic Arts"
  },
  "dom_model": {
    "source_present": true,
    "source_citations": [
      {
        "file": "dom_model4.txt",
        "line_range": "L8-L10",
        "quoted_text": "EA SPORTS Madden NFL 27 / Electronic Arts"
      }
    ],
    "verifier_caught": false,
    "verifier_evidence_excerpt": "publisher value is not present"
  },
  "classification": "DOM_MISSED_SCREENSHOT_CAUGHT",
  "advantage": "SCREENSHOT"
}
```

## Source presence and verifier recovery

For each modality, two questions are answered independently:

1. `source_present`: Is the required value/state actually available in that representation?
2. `verifier_caught`: Did that verifier correctly identify and use the available value/state?

Rules:

- `source_present: false` is a capture or representation limitation, not a verifier miss.
- `source_present: true` and `verifier_caught: false` is a verifier miss.
- A score difference alone does not determine either field.
- A verifier excerpt must come from the existing output; it cannot be rewritten as if the verifier said something else.
- Screenshot citations identify a canonical `screenshotN.png` file and visible locator/text.
- DOM citations identify a canonical `dom_modelN.txt` file, valid line range, and exact quote.
- A confirmed review cannot mark missing source evidence as caught.

## Six classifications

| Classification | Screenshot | DOM model | Advantage |
|---|---|---|---|
| `BOTH_CAUGHT` | Present and caught | Present and caught | Tie |
| `SCREENSHOT_MISSED_DOM_CAUGHT` | Present but missed | Present and caught | DOM |
| `DOM_MISSED_SCREENSHOT_CAUGHT` | Present and caught | Present but missed | Screenshot |
| `BOTH_MISSED` | Present but missed | Present but missed | Neither |
| `SCREENSHOT_EVIDENCE_MISSING` | Missing | Any DOM state | Not a screenshot-verifier error |
| `DOM_EVIDENCE_MISSING` | Present in screenshot | Missing | Not a DOM-verifier error |

If evidence is absent from both sources, both presence fields remain false and the existing screenshot-first classification precedence produces `SCREENSHOT_EVIDENCE_MISSING`; the record is excluded from common-evidence comparison metrics.

## Strongest representation-advantage case

A confirmed DOM advantage requires all three conditions:

1. Human review confirms the exact value/state is visible in a canonical screenshot.
2. The existing screenshot verifier fails to recover it or recovers it incorrectly.
3. The existing DOM verifier correctly recovers it and its claim is supported by an exact DOM-state citation.

The reverse conditions establish a screenshot advantage.

## Workflow

```text
existing screenshot result + existing DOM result
                    │
                    v
      criterion context extracted verbatim
                    │
                    v
 reviewer adds concrete evidence-item rows
                    │
                    v
 source citations and verifier excerpts validated
                    │
                    v
 deterministic classification and advantage
                    │
                    v
 evidence-item table and recovery metrics
```

The audit template includes every criterion, its exact rubric text, both final criterion scores, selected frame/state indices, and all existing verifier evidence analyses. The reviewer then adds only the concrete evidence-item rows needed to explain what was present, caught, missed, or unavailable.

## Metrics

The primary comparison denominator is evidence items confirmed present in both representations.

```text
DOM recovery of screenshot misses =
  SCREENSHOT_MISSED_DOM_CAUGHT
  / (SCREENSHOT_MISSED_DOM_CAUGHT + BOTH_MISSED)

Screenshot recovery of DOM misses =
  DOM_MISSED_SCREENSHOT_CAUGHT
  / (DOM_MISSED_SCREENSHOT_CAUGHT + BOTH_MISSED)

DOM common-evidence catch rate =
  items present in both and caught by DOM
  / items present in both

Screenshot common-evidence catch rate =
  items present in both and caught by screenshot
  / items present in both
```

Reports also show counts for all six classifications, DOM advantages, screenshot advantages, ties, evidence missing by modality, invalid citations, and pending evidence items. Every percentage includes its numerator and denominator; zero denominators produce `N/A`.

## Artifacts

```text
results/<task>/<run-id>/evidence_error_audit/
├── criterion_audit.json
├── evidence_item_review.json
├── evidence_item_audit.json
├── evidence_error_metrics.json
└── evidence_error_report.md
```

- `criterion_audit.json` preserves the existing verifier outputs side by side.
- `evidence_item_review.json` is the editable manual evidence-item template.
- `evidence_item_audit.json` contains validated classifications and advantages.
- Metrics and Markdown are derived only from confirmed evidence items.

## Offline validation

Tests must prove:

- Only canonical, non-symlink `screenshotN.png` and `dom_modelN.txt` sources are inventoried.
- Screenshot and DOM citations reference existing canonical files.
- DOM line ranges are valid and quotes occur within those lines.
- Verifier excerpts occur verbatim in that modality’s extracted outputs.
- Missing source evidence cannot be marked caught.
- All six classifications and advantage labels are deterministic.
- Missing-source items are excluded from common-evidence denominators.
- No audit module imports either verifier or any LLM client.
- Both verifier package manifests remain unchanged before and after implementation.

## Interpretation boundary

The result can say that one representation exceeded the other for a specific, human-confirmed evidence item. It cannot infer representation quality from final scores alone, treat absent source evidence as a verifier error, or claim general superiority from a small denominator.

The next concrete check after implementation is to express task1’s publisher, developer, and release-date requirement as three separate evidence items and verify that the report identifies the precise publisher recovery difference without hiding it inside the criterion’s aggregate score.
