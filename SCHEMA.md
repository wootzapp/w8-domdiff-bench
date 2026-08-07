# DOM diff schema contract

`dom_diff_schema.py` is the supported integration point for verifier tooling.
Import `validate()`, `is_cross_document()`, and `iter_evidence_entries()` from
that module instead of branching directly on the raw JSON shape.

`ARTIFACT_VERSION` is currently `1.0`. New artifacts write both
`artifact_version` and the legacy `schema_version`; older artifacts with only
`schema_version: "1.0"` are still accepted.

## Shared fields

| Field | Type | Presence | Meaning |
|---|---:|---|---|
| `artifact_version` | string | always on new artifacts | Version of this verifier contract. |
| `schema_version` | string | legacy/compatibility | Accepted alias for `artifact_version`. |
| `method` | string | always | Must be `local_slim_dom_semantic_diff`. |
| `captured_at` | string | always | UTC timestamp. |
| `cross_document` | bool | always | Chooses the same-document or cross-document shape. |
| `navigation` | object | always | URL/title/loader transition metadata. |
| `source` | object | always | Before/after source URLs, titles, node counts, and `compareDOMState` metadata. |
| `frames` | object | always | Frame coverage: `count`, `child_frames`, `traversed`, `coverage`, URLs, shadow-DOM declaration. |
| `enrichment` | object | always | Form-property enrichment provenance for `value`, `checked`, `selected`. |
| `key_population` | object | always | Population rates for DOM keys used by the projection. |
| `stats` | object | always | True totals, emitted counts, truncation, and suppression flags. |
| `paths` | object | compact artifacts | Short id to full DOM path map for ids referenced in entries. |

## Same-document shape

Same-document diffs keep node identity and emit semantic changes only.

| Field | Type | Presence | Meaning |
|---|---:|---|---|
| `added` | array | always | Added nodes or collapse/group roots. |
| `removed` | array | always | Removed nodes or collapse/group roots. |
| `changed` | array | always | Changed nodes. `kind` uses `text`, `visibility`, `moved`, `attr:<name>`, or `style:<prop>`. |
| `flagged_changes` | array | always | Emitted but flagged changes, currently scroll-spy `active/current` class churn. |

Example from a real TodoMVC run:

```json
{
  "cross_document": false,
  "added": [{"id": "n5", "tag": "li", "visible_text": "walk dog walk dog"}],
  "changed": [{"id": "n1", "tag": "span", "kind": ["text"], "changes": {"text": {"before": "3 items left", "after": "4 items left"}}}],
  "stats": {"added_total": 7, "changed_total": 4, "truncated": false}
}
```

## Cross-document shape

Cross-document diffs intentionally abandon node matching because structural
paths collide across unrelated documents. The evidence is document-level text
delta plus top new-page actions.

| Field | Type | Presence | Meaning |
|---|---:|---|---|
| `text_delta` | object | always | `added` and `removed` text lines from the new/old documents. |
| `document` | object | compact artifacts | Removed and added node counts. |
| `top_actions` | array | compact artifacts | Up to 10 labelled actions from the new document. |
| `document_added` / `document_removed` | object | full artifacts | Expanded document summaries when `--dom-diff-verbosity full` is used. |
| `interactive_added` | array | full artifacts | Expanded action list when `--dom-diff-verbosity full` is used. |

Example from a real Books to Scrape navigation:

```json
{
  "cross_document": true,
  "navigation": {"from_url": "https://books.toscrape.com/...", "to_url": "https://books.toscrape.com/.../index.html"},
  "document": {"removed_nodes": 580, "added_nodes": 257},
  "text_delta": {"added": ["£43.30", "In stock (15 available)", "9270575728a13a61"], "removed": ["Ready Player One"]},
  "top_actions": [{"id": "n1", "tag": "button", "text": "Add to basket"}],
  "stats": {"added_total": 258, "removed_total": 581, "truncated": true}
}
```

## Normalized evidence stream

`iter_evidence_entries(diff)` flattens both shapes into:

```json
{"kind": "text_added", "text": "£43.30", "element": null, "source": "text_delta.added"}
```

`kind` is one of:

- `text_added`
- `text_removed`
- `element_added`
- `element_removed`
- `element_changed`
- `collapse_root`
- `document_text`

Verifier code should build on this stream so it does not need to know whether
the step was same-document or cross-document.
