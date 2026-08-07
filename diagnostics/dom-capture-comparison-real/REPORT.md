# Real-binary DOM capture comparison

This report replaces the Python-reconstructed simulation now retained at
`diagnostics/dom-capture-comparison-simulated/`. It measures the live
`ChromiumRL.captureStructuredSnapshot` command alongside raw
`ChromiumRL.saveDOMState` and `ChromiumRL.getAgentObservation` captures. No
recorder, production recording path, or DOM-diff builder was modified.

## Executive result

For DOM-diff evidence, the ranking is:

1. **Best — `saveDOMState` plus the current compare/diff pipeline.** It is the
   only source here with structural paths and the unfiltered `class` attribute.
   It proves the class-only one-star rating and preserves cross-document
   matchability.
2. **Second — `getAgentObservation`.** It has stable selectors on these pages
   and is the only raw source that records live typed values (`wrong`) on both
   form fields, but its interactive/content filtering and deduplication lose
   class-only state.
3. **Worst for DOM diff — `captureStructuredSnapshot`.** It has no structural
   path key, filters out `class`, and does not expose live input values.

The decisive number is **0 matched structured-snapshot nodes on every one of
the five cross-document steps (0.0% each)**. The real binary therefore
confirms, rather than refutes, the simulation's headline identity result.

That does not make structured snapshot useless. It is a strong
**agent-observation/semantic-layer** candidate: it carries an explicit tree,
ARIA roles, semantic boundaries, action types, repeated groups, geometry, and
visibility/hit-test information. Its advantage is semantic organization for an
agent, not durable identity or complete DOM evidence for a verifier.

Terminology: `compareDOMState` is a differ over a baseline created from
`saveDOMState`; it is not a third capture representation. In this report,
“Saved DOM/current diff” means the `saveDOMState` representation used by that
pipeline. The third requested representation is `getAgentObservation`.

## 0. Live-build verification

Probe: `ChromiumRL.captureStructuredSnapshot` on
`https://books.toscrape.com/`, using the live browser
`Chrome/152.0.7948.0`. The raw response is in `build-verification.json`.

| check | result |
|---|---|
| command responds, no `-32601` | **pass** |
| non-empty `snapshot.nodes` | **pass: 522 nodes** |
| PageNode has `ref`, `nodeId`, `backendNodeId`, `selectedAttributes`, `states`, `actionTypes` | **pass** |
| at least one `backendNodeId != nodeId` | **FAIL: 0 of 522** |
| `stats.droppedForTextBudget` present | **FAIL: absent** |
| `stats.traversedNodeCount` present | **FAIL: absent** |
| `occluded` absent from PageNode | **FAIL: present on 522 of 522** |

> **The running binary does not contain Pass A's B1, B3, B4, or B12 fixes.**
> In particular, every measured PageNode has `backendNodeId == nodeId`, so all
> id-based results below measure the unfixed identifier implementation. The
> measurement continued as requested.

The live stats still use the older shape:

```json
{
  "rawNodes": 1403,
  "returnedNodes": 522,
  "textChars": 13328,
  "groups": 3,
  "droppedHidden": 147,
  "droppedOffscreen": 0,
  "droppedDuplicate": 0,
  "truncated": false
}
```

## 1. Capture setup

Both tasks were newly executed by `gpt-5.1` (resolved response model
`gpt-5.1-2025-11-13`). At every existing before/after action boundary the
diagnostic wrapper made three independent raw CDP calls:

- `ChromiumRL.saveDOMState` with `{}`.
- `ChromiumRL.getAgentObservation` with
  `{"includeContent":true,"maxElements":250,"maxInteractiveElements":250}`.
- `ChromiumRL.captureStructuredSnapshot` with `{}`. Live defaults were used:
  `maxNodes=700` and `maxTextChars=24000`.

Task A reached the second Mystery book, **In a Dark, Dark Wood**, with price
**£19.63**, availability **In stock (18 available)**, and the class-only rating
`star-rating One`. Task B filled username/password with `wrong`, submitted, and
reached a page containing `Logout` and the quotes text.

Raw compound captures are the `capture_before.json.gz` and
`capture_after.json.gz` files below `tasks/*/step_*`. All **42 before/after
method calls** succeeded, as did all six final-state calls.

## 2. One differ, representation-native identities

One normalization/matching/change implementation was used for all three
sources. The only identity choices were:

| source | keys used, in preference order |
|---|---|
| `saveDOMState` | `stablePath`, `cssSelector`, `xpath`, `fingerprint` |
| `getAgentObservation` | `selector`, `fingerprint` |
| `captureStructuredSnapshot` | `nodeId`, `backendNodeId`, `ref` |

No path was invented from structured snapshot's parent refs. “Changed” compares
the normalized source fields after a match. Counts are captured records; key
collisions are retained in `match_details.json`, rather than silently claimed
as matches.

## 3. Results

### 3.1 Matchability

Each cell is `before → after; matched (rate); +added / −removed / changed`.

| task/step | transition | Saved DOM/current diff | Agent observation | Structured snapshot |
|---|---|---|---|---|
| A/1 navigate home | cross-document | 3→704; 1 (33.3%); +543/−2/0 | 0→144; 0 (0.0%); +144/−0/0 | 2→522; **0 (0.0%)**; +522/−2/0 |
| A/2 click Mystery | cross-document | 704→708; 544 (77.3%); +3/−0/208 | 144→148; 141 (97.9%); +7/−3/118 | 522→526; **0 (0.0%)**; +526/−522/0 |
| A/3 click second book | cross-document | 708→284; 38 (13.4%); +175/−509/17 | 148→43; 4 (9.3%); +39/−144/4 | 526→191; **0 (0.0%)**; +191/−526/0 |
| B/1 navigate login | cross-document | 3→45; 3 (100.0%); +30/−0/0 | 0→11; 0 (0.0%); +11/−0/0 | 2→36; **0 (0.0%)**; +36/−2/0 |
| B/2 fill username | same-document | 45→45; 33 (73.3%); +0/−0/0 | 11→11; 11 (100.0%); +0/−0/**1** | 36→36; 36 (100.0%); +0/−0/**0** |
| B/3 fill password | same-document | 45→45; 33 (73.3%); +0/−0/0 | 11→11; 11 (100.0%); +0/−0/**1** | 36→36; 36 (100.0%); +0/−0/**0** |
| B/4 submit | cross-document | 45→284; 15 (33.3%); +146/−18/0 | 11→63; 4 (36.4%); +59/−7/0 | 36→254; **0 (0.0%)**; +254/−36/0 |

The real result confirms the simulated result: structured snapshot matched
0.0% on all cross-document transitions. On the two same-document fills it
matched 100% by id, but still reported zero changes.

### 3.2 Provability

This table asks whether the raw representation contains evidence from which the
fact can be proved. It does not credit recorder-side enrichment to a raw CDP
method.

| fact | Saved DOM/current diff | Agent observation | Structured snapshot |
|---|---|---|---|
| title: `In a Dark, Dark Wood` | **provable** | **provable** | **provable** |
| price: `£19.63` | **provable** | **provable** | **provable** |
| availability: `In stock (18 available)` | **provable** | **provable** | **provable** |
| rating: class `star-rating One` | **provable** | **not provable — class-only node is filtered from this observation** | **not provable — node is captured, but `class` is filtered from `selectedAttributes`** |
| username value after fill | **not provable from raw call — live property is absent** | **provable — `value:"wrong"`** | **not provable — live value is absent from attributes and states** |
| password value after fill | **not provable from raw call — live property is absent** | **provable — live value changes** | **not provable — live value is absent from attributes and states** |
| post-submit page text (`Logout`) | **provable** | **provable** | **provable** |

There was no node-cap, text-budget, or hidden-filter explanation for the failed
rating and input-value facts. They fail because the relevant attribute/property
is not represented. The earlier simulation's claim that Saved DOM directly
proved typed values mixed in recorder-side form enrichment; the fresh raw
`saveDOMState` response does not. That simulated conclusion is corrected here.

### 3.3 Typed form value: exact real PageNode

Before the username fill:

```json
{
  "ref": "e18",
  "index": 18,
  "nodeId": 6,
  "backendNodeId": 6,
  "parentRef": "n15",
  "childRefs": [],
  "sourceOrder": 52,
  "tag": "input",
  "role": "textbox",
  "selectedAttributes": [
    {"name": "type", "value": "text"},
    {"name": "name", "value": "username"}
  ],
  "states": [],
  "actionTypes": ["click", "type", "focus"],
  "bounds": {"x": 105.5, "y": 145.9375, "width": 262.5, "height": 40},
  "clippedBounds": {"x": 105.5, "y": 145.9375, "width": 262.5, "height": 40},
  "visible": true,
  "inViewport": true,
  "occluded": false,
  "hitTestable": true,
  "scrollable": false,
  "confidence": 0.92,
  "truncated": false
}
```

After filling `wrong`:

```json
{
  "ref": "e18",
  "index": 18,
  "nodeId": 6,
  "backendNodeId": 6,
  "parentRef": "n15",
  "childRefs": [],
  "sourceOrder": 52,
  "tag": "input",
  "role": "textbox",
  "selectedAttributes": [
    {"name": "type", "value": "text"},
    {"name": "name", "value": "username"}
  ],
  "states": [],
  "actionTypes": ["click", "type", "focus"],
  "bounds": {"x": 105.5, "y": 145.9375, "width": 262.5, "height": 40},
  "clippedBounds": {"x": 105.5, "y": 145.9375, "width": 262.5, "height": 40},
  "visible": true,
  "inViewport": true,
  "occluded": false,
  "hitTestable": true,
  "scrollable": false,
  "confidence": 0.92,
  "truncated": false
}
```

The records are byte-for-byte semantically identical. `value` appears nowhere
in `selectedAttributes`; `states` is empty before and after. Meanwhile the
agent observation changes from `value:""` to `value:"wrong"`.

**Answer: the real `captureStructuredSnapshot` does not detect a typed form
value.** The simulated zero-change finding was not an artifact.

### 3.4 Coverage and truncation

Agent-observation cells show `interactive+content; hidden/empty/duplicate`.
Structured cells show `returned/raw; hidden/offscreen/duplicate; text chars`.

| step | agent observation before → after | structured snapshot before → after |
|---|---|---|
| A/1 | 0+0; 1/0/0 → 104+40; 25/20/**29** | 2/4; 1/0/0; 0 → 522/1403; 147/0/0; 13,328 |
| A/2 | 104+40; 25/20/**29** → 108+40; 25/20/**26** | 522/1403; 147/0/0; 13,328 → 526/1412; 150/0/0; 13,451 |
| A/3 | 108+40; 25/20/**26** → 20+23; 23/7/**7** | 526/1412; 150/0/0; 13,451 → 191/556; 66/0/0; 7,215 |
| B/1 | 0+0; 1/0/0 → 7+4; 6/0/0 | 2/4; 1/0/0; 0 → 36/91; 20/0/0; 416 |
| B/2 | 7+4; 6/0/0 → same | 36/91; 20/0/0; 416 → same |
| B/3 | 7+4; 6/0/0 → same | 36/91; 20/0/0; 416 → same |
| B/4 | 7+4; 6/0/0 → 57+6; 17/0/**8** | 36/91; 20/0/0; 416 → 254/468; 71/0/0; 7,697 |

`saveDOMState` captured 3→704, 704→708, 708→284, 3→45,
45→45, 45→45, and 45→284 nodes respectively; its response reports no filter
or cap counters.

No 250-element observation cap fired. No structured capture reported
`truncated:true`; returned nodes peaked at 526 and text at 13,451, below the
700/24,000 defaults. Neither test site produced 700 returned candidates, so
this run says **nothing** about whether the 700-node cap is harmless on larger
pages. The old live stats cannot distinguish the large remainder between
`rawNodes` and returned nodes beyond the reported hidden/offscreen/duplicate
counters; it would be dishonest to assign those nodes to B4's absent text-budget
counter.

### 3.5 Payload size

Each cell is `raw/gzip bytes`, before → after. Raw means compact JSON for the
method payload, not the outer diagnostic wrapper.

| step | Saved DOM/current diff | Agent observation | Structured snapshot |
|---|---|---|---|
| A/1 | 2,118/597 → 827,715/28,480 | 452/261 → 70,591/7,310 | 1,085/456 → 285,029/24,241 |
| A/2 | 827,715/28,480 → 832,141/28,816 | 70,591/7,310 → 71,802/7,427 | 285,029/24,241 → 286,788/24,458 |
| A/3 | 832,141/28,816 → 326,206/14,581 | 71,802/7,427 → 21,140/3,017 | 286,788/24,458 → 105,997/10,136 |
| B/1 | 2,118/597 → 38,754/3,113 | 452/261 → 3,840/1,081 | 1,085/456 → 17,629/2,161 |
| B/2 | 38,754/3,113 → 38,754/3,123 | 3,840/1,081 → 3,845/1,084 | 17,629/2,164 → 17,629/2,161 |
| B/3 | 38,754/3,123 → 38,754/3,123 | 3,845/1,084 → 3,850/1,085 | 17,629/2,161 → 17,629/2,162 |
| B/4 | 38,754/3,123 → 283,972/13,233 | 3,850/1,085 → 31,531/4,542 | 17,629/2,161 → 133,921/12,844 |

Structured snapshot is smaller than Saved DOM raw JSON, but materially larger
than its simulation: approximately +90% on the books homepage, +90% on the
category, +84% on the product, +78% on login, and +130% on the quotes page.
The main reason is that the real command returned substantially more PageNodes
and richer per-node fields than the reconstruction.

### 3.6 Class-only star element, complete records

`saveDOMState`:

```json
{
  "nodeId": 1609,
  "tagName": "P",
  "parentId": 1574,
  "siblingIndex": 0,
  "stablePath": "html.no-js > body#default > div.container-fluid > div.page_inner > div.content > div#content_inner > article.product_page > div.row:nth-of-type(1) > div.col-sm-6:nth-of-type(2) > p.star-rating",
  "cssSelector": "html.no-js > body#default > div.container-fluid > div.page_inner > div.content > div#content_inner > article.product_page > div.row:nth-of-type(1) > div.col-sm-6:nth-of-type(2) > p.star-rating",
  "xpath": "/html[1]/body[1]/div[1]/div[1]/div[2]/div[2]/article[1]/div[1]/div[2]/p[3]",
  "attributes": [{"name": "class", "value": "star-rating One"}],
  "textContent": " ",
  "bounds": {"x": 690.5, "y": 371.359375, "width": 580, "height": 20},
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

`getAgentObservation`:

```json
null
```

`captureStructuredSnapshot`:

```json
{
  "ref": "n42",
  "index": 42,
  "nodeId": 1609,
  "backendNodeId": 1609,
  "parentRef": "n35",
  "childRefs": [],
  "sourceOrder": 128,
  "tag": "p",
  "role": "generic",
  "directText": " ",
  "subtreeText": " ",
  "selectedAttributes": [],
  "states": [],
  "actionTypes": [],
  "bounds": {"x": 690.5, "y": 371.359375, "width": 580, "height": 20},
  "clippedBounds": {"x": 690.5, "y": 371.359375, "width": 580, "height": 20},
  "visible": true,
  "inViewport": true,
  "occluded": false,
  "hitTestable": true,
  "scrollable": false,
  "repeatedGroupId": "rg3",
  "repeatedItemIndex": 2,
  "confidence": 0.72,
  "truncated": false
}
```

The structured command did capture the exact `<p>`, but recorded neither its
class nor any equivalent rating state. That empty semantic payload is the
clearest concrete example of why it is weaker verifier evidence.

### 3.7 Real versus simulated

| headline | simulated | real | explanation |
|---|---:|---:|---|
| structured cross-document match | 0.0% on all 5 steps | **0.0% on all 5 steps** | confirmed: available ids are document-local and no path exists |
| structured same-document fills | 100% matched, 0 changed | **100% matched, 0 changed** | confirmed: typed value is absent |
| structured homepage nodes | 398 | **522** | simulation under-approximated live candidates |
| structured category nodes | 401 | **526** | same |
| structured product nodes | 146 | **191** | same |
| structured login nodes | 27 | **36** | same |
| structured quotes-page nodes | 145 | **254** | largest coverage miss in simulation |
| homepage structured raw bytes | 150,094 | **285,029** | more/richer real nodes |
| quotes structured raw bytes | 58,215 | **133,921** | more/richer real nodes |
| class-only star | not provable | **not provable** | confirmed attribute filtering |
| raw Saved DOM typed values | reported provable | **not provable** | simulation report accidentally credited recorder enrichment |

The simulation was trustworthy for the qualitative loss modes—cross-document
identity, class filtering, and typed-value omission—but not for coverage or
payload size. Future simulations of this format should be treated as design
probes, not quantitative measurements.

## 4. Verdict and the value of the worst method

### DOM-diff suitability

1. **Saved DOM/current diff is best** because structural paths survive enough
   navigation churn to match nodes and its broad attributes preserve class-only
   UI state. It is the only method that proves all four Task A facts.
2. **Agent observation is second** because selector identity and live form
   values are excellent for interaction changes, but filtering/dedup makes it
   incomplete evidence. It proved six of seven tested facts and uniquely proved
   both raw typed values.
3. **Structured snapshot is worst** because its only identities are
   document-local ids/refs and its semantic projection deliberately discards
   evidence such as `class` and live `value`. Its decisive failure is **zero
   matches in five out of five cross-document steps**.

### What structured snapshot is good at

It is substantially better shaped for an agent to reason over than a flat raw
DOM dump. The real captures produced:

| page | nodes | parent/child edges | nodes with ARIA role | semantic boundaries | action nodes (entries) | state entries | table nodes / TableInfo | scrollable | repeated nodes / groups |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| books home | 522 | 521 | 378 | 96 | 114 (114) | 0 | 0 / 0 | 0 | 73 / 3 |
| Mystery | 526 | 525 | 381 | 97 | 115 (115) | 0 | 0 / 0 | 0 | 76 / 4 |
| product | 191 | 190 | 139 | 39 | 22 (22) | 0 | 1 / 0 | 0 | 24 / 5 |
| login | 36 | 35 | 27 | 0 | 7 (13) | 0 | 0 / 0 | 0 | 0 / 0 |
| quotes result | 254 | 253 | 145 | 1 | 65 (65) | 0 | 0 / 0 | 0 | 43 / 8 |

The hierarchy is explicit through `parentRef`/`childRefs`. Roles include links,
buttons, textboxes, alerts, and generics. Boundaries include list items,
articles, sections, rows, and cells. The login page inferred 7 clicks, 3 types,
and 3 focus actions. Repeated-group tagging was active on both content sites.

The requested categories that happened to produce zero must stay explicit:
there were **0 state entries**, **0 scrollable regions**, and **0 structured
TableInfo objects** on these pages. The product page did retain one `<table>`
node with flattened text, but did not emit a TableInfo object. These zeros do
not show the features are broken; they show this two-site sample did not
exercise them as structured outputs.

So the practical advantage of the worst DOM-diff method is clear: use it to
give an agent a compact semantic tree, action affordances, roles, repeated-item
structure, and geometry. Do not use it alone as the verifier's authoritative
change/evidence layer.

## Artifacts and pause point

- `metrics_summary.json`: tables and configurations above.
- `match_details.json`: per-record identity matches/collisions.
- `form_value_records.json`: full three-method form records.
- `star_rating_records.json`: full side-by-side rating records.
- `feature_counts.json`: structured semantic counts.
- `tasks/`: raw fresh Task A and Task B recordings and captures.
- `../dom-capture-comparison-simulated/`: retained, relabelled simulation.

The separate 12-task snapshot-diff experiment is intentionally not included in
this comparison conclusion. It was paused on request and will resume only after
explicit approval.
