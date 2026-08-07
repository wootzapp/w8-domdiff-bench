# SUPERSEDED — Simulated DOM Capture Method Comparison

> **Superseded simulation.** This report reconstructed
> `ChromiumRL.captureStructuredSnapshot` from `saveDOMState` because the command
> was not available in the browser used for this run. The real-binary
> measurement in `diagnostics/dom-capture-comparison-real/REPORT.md` replaces
> its conclusions. This simulation is retained so the simulated-versus-real
> delta remains auditable.

This is a diagnostics-only measurement. No recorder or diff-builder source files were modified.

## Method setup

- `ChromiumRL.saveDOMState`: captured from the running browser via existing `--dom-capture full` artifacts (`dom_before_raw.json.gz` / `dom_after_raw.json.gz`).
- `ChromiumRL.getAgentObservation`: captured from the running browser via `--keep-observations` artifacts.
- `ChromiumRL.captureStructuredSnapshot`: unavailable in the running binary, so it was simulated from `saveDOMState` using the documented reference filters in `reference/dom-refinement/chromium/inspector_chromiumrl_agent.cc`. Simulated raw outputs are in `diagnostics/dom-capture-comparison/structured_simulated/`.

### Structured-snapshot simulation fidelity

Implemented filters: decorative/unsupported node dropping; hidden/style/aria-hidden dropping; no-box-and-no-text dropping; structured candidate filtering; hard 700-node traversal-order cap; 24,000-character text budget; 240/500 direct/subtree text caps; selected-attribute allow-list without `class` or `id`; no computed-style fields; identity limited to `nodeId`/`backendNodeId`/`ref`.

Filters/facts that could not be exactly reproduced from `saveDOMState`: Exact LayoutObject availability; approximated from bounds plus text.; Exact Blink accessible-name fallback order; approximated from raw text/selected attributes.; Exact hit-test and compositor occlusion facts; saveDOMState does not expose them for all nodes.; Closed shadow DOM and out-of-process frame internals are unavailable from saveDOMState..

## Matchability

### task-a-books-mystery

| step | method | before | after | matched | match rate | added | removed | changed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| step_001 | saveDOMState | 3 | 704 | 1 | 33.3% | 543 | 2 | 0 |
| step_001 | getAgentObservation | 0 | 114 | 0 | 0.0% | 114 | 0 | 0 |
| step_001 | captureStructuredSnapshot_sim | 2 | 398 | 0 | 0.0% | 398 | 2 | 0 |
| step_002 | saveDOMState | 704 | 708 | 544 | 77.3% | 3 | 0 | 208 |
| step_002 | getAgentObservation | 114 | 114 | 113 | 99.1% | 1 | 1 | 93 |
| step_002 | captureStructuredSnapshot_sim | 398 | 401 | 0 | 0.0% | 401 | 398 | 0 |
| step_003 | saveDOMState | 708 | 283 | 38 | 13.4% | 175 | 509 | 17 |
| step_003 | getAgentObservation | 114 | 22 | 3 | 13.6% | 19 | 111 | 3 |
| step_003 | captureStructuredSnapshot_sim | 401 | 146 | 0 | 0.0% | 146 | 401 | 0 |

### task-b-quotes-login

| step | method | before | after | matched | match rate | added | removed | changed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| step_001 | saveDOMState | 3 | 45 | 3 | 100.0% | 30 | 0 | 0 |
| step_001 | getAgentObservation | 0 | 7 | 0 | 0.0% | 7 | 0 | 0 |
| step_001 | captureStructuredSnapshot_sim | 2 | 27 | 0 | 0.0% | 27 | 2 | 0 |
| step_002 | saveDOMState | 45 | 45 | 33 | 73.3% | 0 | 0 | 1 |
| step_002 | getAgentObservation | 7 | 7 | 7 | 100.0% | 0 | 0 | 1 |
| step_002 | captureStructuredSnapshot_sim | 27 | 27 | 27 | 100.0% | 0 | 0 | 0 |
| step_003 | saveDOMState | 45 | 45 | 33 | 73.3% | 0 | 0 | 1 |
| step_003 | getAgentObservation | 7 | 7 | 7 | 100.0% | 0 | 0 | 1 |
| step_003 | captureStructuredSnapshot_sim | 27 | 27 | 27 | 100.0% | 0 | 0 | 0 |
| step_004 | saveDOMState | 45 | 284 | 15 | 33.3% | 146 | 18 | 0 |
| step_004 | getAgentObservation | 7 | 57 | 2 | 28.6% | 55 | 5 | 0 |
| step_004 | captureStructuredSnapshot_sim | 27 | 145 | 0 | 0.0% | 145 | 27 | 0 |

Cross-document interpretation: `captureStructuredSnapshot_sim` had 0 matched nodes on the observed cross-document steps. That confirms the expected failure mode: nodeId/ref identity is per-document and provides no structural path key for navigation diffs.

## Provability

### Task A final book page

| fact | saveDOMState | getAgentObservation | captureStructuredSnapshot simulated |
|---|---|---|---|
| book title | provable — present in added/changed diff evidence | not provable — present in capture but not provable from identity diff output | provable — present in added/changed diff evidence |
| price | provable — present in added/changed diff evidence | not provable — not captured by this representation | provable — present in added/changed diff evidence |
| availability text | provable — present in added/changed diff evidence | not provable — not captured by this representation | provable — present in added/changed diff evidence |
| star rating class | provable — present in added/changed diff evidence | not provable — hidden/non-interactive text/state not captured in interactive observation | not provable — attribute filtered out: class is intentionally absent from selectedAttributes |

### Task B username fill

| fact | saveDOMState | getAgentObservation | captureStructuredSnapshot simulated |
|---|---|---|---|
| form field value | provable — present in added/changed diff evidence | provable — present in added/changed diff evidence | not provable — value property not mirrored into selectedAttributes by this lossy snapshot source |

### Task B submit result

| fact | saveDOMState | getAgentObservation | captureStructuredSnapshot simulated |
|---|---|---|---|
| post-submit page text | provable — present in added/changed diff evidence | provable — present in added/changed diff evidence | provable — present in added/changed diff evidence |

Note: the actual second Mystery book in this run was `In a Dark, Dark Wood`, whose rating class is `star-rating One`. The user-provided `star-rating Three` example is still the discriminating property: the rating is class-only, and structured snapshot selected attributes intentionally exclude `class`.

## Coverage and truncation

### task-a-books-mystery

| step | method | before captured | after captured | before dropped/truncation | after dropped/truncation |
|---|---:|---:|---:|---|---|
| step_001 | saveDOMState | 3 | 704 | dropped={}, trunc={'fired': False} | dropped={}, trunc={'fired': False} |
| step_001 | getAgentObservation | 0 | 114 | dropped={'droppedHidden': 1, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 0}, trunc={'fired': False, 'cap': 250} | dropped={'droppedHidden': 25, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 0}, trunc={'fired': False, 'cap': 250} |
| step_001 | captureStructuredSnapshot_sim | 2 | 398 | dropped={'decorative_or_unsupported': 1}, trunc={'node_cap': False, 'text_budget': False} | dropped={'hidden_style_or_aria': 163, 'decorative_or_unsupported': 19, 'no_box_and_no_text': 4, 'not_candidate': 120}, trunc={'node_cap': False, 'text_budget': False} |
| step_002 | saveDOMState | 704 | 708 | dropped={}, trunc={'fired': False} | dropped={}, trunc={'fired': False} |
| step_002 | getAgentObservation | 114 | 114 | dropped={'droppedHidden': 25, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 0}, trunc={'fired': False, 'cap': 250} | dropped={'droppedHidden': 25, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 1}, trunc={'fired': False, 'cap': 250} |
| step_002 | captureStructuredSnapshot_sim | 398 | 401 | dropped={'hidden_style_or_aria': 163, 'decorative_or_unsupported': 19, 'no_box_and_no_text': 4, 'not_candidate': 120}, trunc={'node_cap': False, 'text_budget': False} | dropped={'hidden_style_or_aria': 164, 'decorative_or_unsupported': 19, 'no_box_and_no_text': 4, 'not_candidate': 120}, trunc={'node_cap': False, 'text_budget': False} |
| step_003 | saveDOMState | 708 | 283 | dropped={}, trunc={'fired': False} | dropped={}, trunc={'fired': False} |
| step_003 | getAgentObservation | 114 | 22 | dropped={'droppedHidden': 25, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 1}, trunc={'fired': False, 'cap': 250} | dropped={'droppedHidden': 23, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 0}, trunc={'fired': False, 'cap': 250} |
| step_003 | captureStructuredSnapshot_sim | 401 | 146 | dropped={'hidden_style_or_aria': 164, 'decorative_or_unsupported': 19, 'no_box_and_no_text': 4, 'not_candidate': 120}, trunc={'node_cap': False, 'text_budget': False} | dropped={'hidden_style_or_aria': 72, 'decorative_or_unsupported': 19, 'no_box_and_no_text': 3, 'not_candidate': 43}, trunc={'node_cap': False, 'text_budget': False} |

### task-b-quotes-login

| step | method | before captured | after captured | before dropped/truncation | after dropped/truncation |
|---|---:|---:|---:|---|---|
| step_001 | saveDOMState | 3 | 45 | dropped={}, trunc={'fired': False} | dropped={}, trunc={'fired': False} |
| step_001 | getAgentObservation | 0 | 7 | dropped={'droppedHidden': 1, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 0}, trunc={'fired': False, 'cap': 250} | dropped={'droppedHidden': 6, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 0}, trunc={'fired': False, 'cap': 250} |
| step_001 | captureStructuredSnapshot_sim | 2 | 27 | dropped={'decorative_or_unsupported': 1}, trunc={'node_cap': False, 'text_budget': False} | dropped={'hidden_style_or_aria': 13, 'decorative_or_unsupported': 5}, trunc={'node_cap': False, 'text_budget': False} |
| step_002 | saveDOMState | 45 | 45 | dropped={}, trunc={'fired': False} | dropped={}, trunc={'fired': False} |
| step_002 | getAgentObservation | 7 | 7 | dropped={'droppedHidden': 6, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 0}, trunc={'fired': False, 'cap': 250} | dropped={'droppedHidden': 6, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 0}, trunc={'fired': False, 'cap': 250} |
| step_002 | captureStructuredSnapshot_sim | 27 | 27 | dropped={'hidden_style_or_aria': 13, 'decorative_or_unsupported': 5}, trunc={'node_cap': False, 'text_budget': False} | dropped={'hidden_style_or_aria': 13, 'decorative_or_unsupported': 5}, trunc={'node_cap': False, 'text_budget': False} |
| step_003 | saveDOMState | 45 | 45 | dropped={}, trunc={'fired': False} | dropped={}, trunc={'fired': False} |
| step_003 | getAgentObservation | 7 | 7 | dropped={'droppedHidden': 6, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 0}, trunc={'fired': False, 'cap': 250} | dropped={'droppedHidden': 6, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 0}, trunc={'fired': False, 'cap': 250} |
| step_003 | captureStructuredSnapshot_sim | 27 | 27 | dropped={'hidden_style_or_aria': 13, 'decorative_or_unsupported': 5}, trunc={'node_cap': False, 'text_budget': False} | dropped={'hidden_style_or_aria': 13, 'decorative_or_unsupported': 5}, trunc={'node_cap': False, 'text_budget': False} |
| step_004 | saveDOMState | 45 | 284 | dropped={}, trunc={'fired': False} | dropped={}, trunc={'fired': False} |
| step_004 | getAgentObservation | 7 | 57 | dropped={'droppedHidden': 6, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 0}, trunc={'fired': False, 'cap': 250} | dropped={'droppedHidden': 17, 'droppedOffscreen': 0, 'droppedCovered': 0, 'droppedEmpty': 0, 'droppedDuplicate': 8}, trunc={'fired': False, 'cap': 250} |
| step_004 | captureStructuredSnapshot_sim | 27 | 145 | dropped={'hidden_style_or_aria': 13, 'decorative_or_unsupported': 5}, trunc={'node_cap': False, 'text_budget': False} | dropped={'hidden_style_or_aria': 124, 'decorative_or_unsupported': 15}, trunc={'node_cap': False, 'text_budget': False} |

For `getAgentObservation`, `droppedDuplicate` is reported by the browser stats, but the payload does not include the dropped elements. Exact names of deduplicated examples are therefore unavailable from the artifact. Non-zero counts occurred on Task A step_002 after (`droppedDuplicate=1`) and Task B step_004 after (`droppedDuplicate=8`); likely repeated-label pressure on these pages includes repeated author/about links and repeated category/navigation labels, but the exact dropped records are not emitted and cannot be named faithfully.

## Size

### task-a-books-mystery

| step | method | before raw bytes | before gzip bytes | after raw bytes | after gzip bytes |
|---|---:|---:|---:|---:|---:|
| step_001 | saveDOMState | 2118 | 598 | 827710 | 28604 |
| step_001 | getAgentObservation | 582 | 326 | 63045 | 6515 |
| step_001 | captureStructuredSnapshot_sim | 1254 | 620 | 150094 | 14289 |
| step_002 | saveDOMState | 827710 | 28604 | 832061 | 28796 |
| step_002 | getAgentObservation | 63045 | 6515 | 61784 | 6399 |
| step_002 | captureStructuredSnapshot_sim | 150094 | 14289 | 151051 | 14378 |
| step_003 | saveDOMState | 832061 | 28796 | 325108 | 14500 |
| step_003 | getAgentObservation | 61784 | 6399 | 13650 | 2031 |
| step_003 | captureStructuredSnapshot_sim | 151051 | 14378 | 57600 | 6236 |

### task-b-quotes-login

| step | method | before raw bytes | before gzip bytes | after raw bytes | after gzip bytes |
|---|---:|---:|---:|---:|---:|
| step_001 | saveDOMState | 2118 | 598 | 39405 | 3276 |
| step_001 | getAgentObservation | 582 | 326 | 3326 | 1045 |
| step_001 | captureStructuredSnapshot_sim | 1254 | 620 | 9918 | 1690 |
| step_002 | saveDOMState | 39405 | 3276 | 39410 | 3291 |
| step_002 | getAgentObservation | 3326 | 1045 | 3331 | 1049 |
| step_002 | captureStructuredSnapshot_sim | 9918 | 1690 | 9918 | 1690 |
| step_003 | saveDOMState | 39410 | 3291 | 39409 | 3285 |
| step_003 | getAgentObservation | 3331 | 1049 | 3336 | 1051 |
| step_003 | captureStructuredSnapshot_sim | 9918 | 1690 | 9918 | 1690 |
| step_004 | saveDOMState | 39409 | 3285 | 283978 | 13245 |
| step_004 | getAgentObservation | 3336 | 1051 | 29178 | 4262 |
| step_004 | captureStructuredSnapshot_sim | 9918 | 1690 | 58215 | 6799 |

## Star-rating element records

### saveDOMState
```json
{
  "nodeId": 1657,
  "tagName": "P",
  "parentId": 1649,
  "siblingIndex": 0,
  "stablePath": "html.no-js > body#default > div.container-fluid > div.page_inner > div.content > div#content_inner > article.product_page > div.row:nth-of-type(1) > div.col-sm-6:nth-of-type(2) > p.star-rating",
  "cssSelector": "html.no-js > body#default > div.container-fluid > div.page_inner > div.content > div#content_inner > article.product_page > div.row:nth-of-type(1) > div.col-sm-6:nth-of-type(2) > p.star-rating",
  "xpath": "/html[1]/body[1]/div[1]/div[1]/div[2]/div[2]/article[1]/div[1]/div[2]/p[3]",
  "attributes": [
    {
      "name": "class",
      "value": "star-rating One"
    }
  ],
  "textContent": "",
  "bounds": {
    "x": 689.5,
    "y": 371.359375,
    "width": 580,
    "height": 20
  },
  "isVisible": true,
  "isInViewport": true,
  "zIndex": 0,
  "keyStyles": {
    "display": "block",
    "color": "rgb(203, 203, 203)",
    "backgroundColor": "rgba(0, 0, 0, 0)",
    "fontSize": "14px",
    "fontWeight": "400",
    "opacity": "1",
    "visibility": "visible",
    "padding": "0px",
    "margin": "0px 0px 20px",
    "width": "580px",
    "height": "20px",
    "position": "static",
    "overflow": "visible",
    "whiteSpace": "normal",
    "textAlign": "start",
    "lineHeight": "20px",
    "textDecoration": "none",
    "border": "0px none rgb(203, 203, 203)",
    "borderRadius": "0px"
  },
  "fingerprint": "P|t: "
}
```
### getAgentObservation
```json
null
```
### captureStructuredSnapshot simulated
```json
{
  "ref": "n33",
  "nodeId": 1657,
  "backendNodeId": 1657,
  "parentNodeId": 1649,
  "sourceOrder": 66,
  "tag": "p",
  "role": "",
  "directText": "",
  "subtreeText": "",
  "selectedAttributes": [],
  "states": [],
  "actionTypes": [],
  "bounds": {
    "x": 689.5,
    "y": 371.359375,
    "width": 580,
    "height": 20
  },
  "visible": true,
  "inViewport": true,
  "hitTestable": null
}
```
## Verdict

1. **Best: `ChromiumRL.saveDOMState`** for DOM-diff evidence. It captures the full DOM node set, structural identity keys, attributes including `class`, and enough non-interactive text to prove title/price/availability/rating/form-result facts. The star rating is provable only here because the evidence is `class="star-rating One"`.
2. **Middle: `ChromiumRL.getAgentObservation`**. It is small and action-oriented, but it is capped/interactive-focused and drops non-interactive DOM state. It could prove some visible text and form values, but not class-only star rating evidence in this task.
3. **Worst: `captureStructuredSnapshot` simulated from the reference design** for verifier DOM diff. It is useful as model observation, but unsuitable as primary DOM-diff evidence because it intentionally removes `class`/`id`, has no structural path identity, and is capped at 700 traversal-order nodes / 24k text chars. The single decisive number here: on Task A step_003 it captured the product page in 146 nodes but still could not prove the class-only star rating because `class` is not in `selectedAttributes`. That is a data-loss problem, not a differ problem.

Plain-language bottom line: **structured snapshot is a good agent-observation candidate, but the worst DOM-diff evidence source, because it deliberately drops exactly the kind of semantic DOM attribute (`class`) needed to prove common UI state such as ratings, selected tabs, and active statuses.**
