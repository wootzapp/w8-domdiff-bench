# Cost estimates

Amounts are **estimated from list prices and explicit usage assumptions**, not measured spend. With one trial per task, all 40 tasks produce 80 scheduled runs across both arms. This estimate assumes one recording per run and no technical rerun. The primary profile is used unless a Pro comparison is explicitly selected. Turn counts, text volume and output volume are planning assumptions; provider receipts determine actual spending.

| Stage | Model | Delivery | Input / output USD per million |
| --- | --- | --- | --- |
| Browser actions | gemini-3.8-flash | Normal | 0.75 / 3.75 (configured introductory tariff) |
| Native screenshot and DOM verifiers | gemini-3.5-flash-lite | Batch | 0.15 / 1.25 |
| Common completion and audit adjudication | gpt-6.1-sol | Batch | 1 / 5 up to 272,000 input tokens; 2 / 7.50 above |
| Audit inventory; optional Pro native profile | gemini-3.1-pro-preview | Batch | 1 / 6 up to 200,000 input tokens; 2 / 9 above |
| Rubric generation and dependency check | gpt-5.2 | Normal | 1.75 / 14 |

The rates above are the tariff constants applied by [`run_metrics.TOKEN_PRICES` and `_price_call()`](../w8bench/verifier/run_metrics.py), not a live provider-price lookup. Receipts identify the [Google](https://ai.google.dev/gemini-api/docs/pricing) and [OpenAI](https://developers.openai.com/api/docs/pricing) price sources. Batch discounts apply only to recorded Batch items. Cached input is a subset of input; thinking/reasoning is a subset of output. Unknown usage prevents an exact cost total; an unrecognized returned model or transport also leaves a call unpriced. Runtime receipts price calls individually using their transport and model; they do not add reasoning tokens twice.

The scenarios assume one execution per arm, no technical rerun, validation repair, caching, free-tier allowance, tax or failed transport spending. Both arms use the same planning turns for a task; actual turns and costs can differ. The ranges vary workload assumptions and are not statistical intervals or guaranteed bounds.

| Difficulty | Low / central / high turns per arm | Frozen criteria assumed | Cost per task, both arms, one trial: low / central / high |
| --- | --- | --- | --- |
| easy | 5 / 10 / 15 | 4 | $0.59 / $0.83 / $1.08 |
| medium | 15 / 28 / 40 | 8 | $1.27 / $1.94 / $3.00 |
| hard | 40 / 70 / 100 | 12 | $3.27 / $6.55 / $8.81 |
| complex | 80 / 115 / 150 | 16 | $7.83 / $10.57 / $13.30 |

## Forty tasks, both arms, one trial

| Stream | Low | Central | High |
| --- | ---: | ---: | ---: |
| DOM-arm actor | $7.72 | $12.29 | $16.81 |
| Screenshot-arm actor | $6.25 | $9.95 | $13.61 |
| Paired completion | $22.19 | $39.25 | $52.24 |
| Audit inventory | $31.67 | $44.75 | $62.20 |
| Audit adjudication | $27.82 | $45.89 | $58.88 |
| Native screenshot verifier | $16.30 | $22.43 | $27.94 |
| Native DOM verifier | $17.73 | $24.33 | $30.18 |
| Google subtotal | $79.67 | $113.75 | $150.74 |
| OpenAI subtotal | $50.01 | $85.14 | $111.13 |
| Total | $129.68 | $198.89 | $261.87 |

For any positive k, the full planning budget is **$2.38 + k × $129.68–$261.87**, with central figure **$2.38 + k × $198.89**. The $2.38 is rubric preparation once for all 40 tasks, not once per trial. The pricing code marks the actor tariff as introductory but does not switch tariffs automatically. These totals use its fixed 0.75/3.75 actor rate; they do not predict spending after that tariff ceases to apply.

## Usage assumptions

Let T be planned actor turns per arm, C assumed frozen criteria, H=120T action-history tokens, D=2,800 DOM tokens/state and I=1,500 judge-image tokens/state. Use N=T+1 as a conservative state-count allowance for this estimate. Actual states follow executed actions, not model turns: rejected and terminal responses consume turns without creating after-states. The image value is an unmeasured planning allowance; provider receipts determine actual image usage. Actor requests assume 4,100 input +650 output tokens per DOM turn and 3,200 input +550 output per screenshot turn. The screenshot actor uses HIGH, with an allowance of 1,100 image tokens and 2,100 text tokens. Judge image settings are HIGH. Output includes thinking.

For each native verifier in each actor run:

| Stage group | Calls | Input per call | Output per call |
| --- | --- | --- | --- |
| Action-only and two validity stages | 3 | 2,000+H+180C | 1,200 |
| Relevance | N | 2,000+180C+P | 100+50C |
| Selected-state analysis | U=min(N,5C) | 2,500+H+P+900C/U | 1,750C/U |
| Summary global checks | 4 | 4,000+H+800C | 1,000+150C |
| Raw-evidence global checks | 2 | 4,000+H+800C+min(UP,85,000) | 1,000+150C |

P is I for the screenshot verifier and D for the DOM verifier. These are cost assumptions, not runtime limits or selection rules. Both native verifiers are invoked for each final recording; the cost scenario assumes the listed stage groups complete. Conditional work, unavailable inputs, failures and overlapping selected states can change actual counts. Selection keeps at most five relevant states per criterion and uses one scoring vote.

Each recording has one common completion call: input N(D+I)+H+7,000+180C, output 1,000+200C. Inventory has one call: input N(D+I)+H+8,000+2,000C, output 1,000+600C. Adjudication has one call: input N(D+I)+H+9,000+3,100C, output 1,000+650C. Rubrics assume two calls per task, together 10,000 input and 3,000 output tokens. Long-context price tiers are evaluated per request.

The native input guard is 115,000 tokens; 85,000 above is a planning evidence allowance, not a runtime cap. The complex central/high raw-evidence formulas predict 115,600/119,800 input tokens, exceeding that guard. Those arithmetic scenarios are not validated request plans. A real native request counted above the guard is refused before dispatch; no chunking or sampling is implied. Exact guard counts use `cl100k_base` text tokens and the native client’s image allowance, rather than the planning image value. Full completion/audit requests are not truncated by the Batch scheduler. The pilot must establish actual request fit and judge agreement before collection; these totals are illustrative spending budgets, not proof that every assumed request is admissible.

## Pro pilot comparison

The comparison adds the Pro native verifier calls and a separate inventory/adjudication for each existing pilot recording. It shares common completion and does not repeat actor work or rubric preparation. These additional requests are excluded from the primary forty-task totals. The comparison report accounts for each profile and shared completion separately.

## Per-call cost accounting

For each call, the estimator subtracts cached and cache-write input from total
input before pricing ordinary input. It prices cached input, cache writes and
output separately, with thinking already included in output. Batch halves input,
output and cached-input tariffs; cache-write tariffs are not halved. Above a
model’s configured long-context threshold, input/cache/write tariffs double and
output is multiplied by 1.5. The code applies an additional write charge to
reported twelve-hour cache-write tokens. Missing cache details are explicitly
priced as ordinary input; unknown input/output usage prevents an exact total.
These are the implemented estimate rules, not a provider invoice.

The [datacard](datacard.md#judge-delivery) defines models and transport; the
[evaluation protocol](evaluation-protocol.md) defines usage coverage and cost
streams. The [runbook](runbook.md#compare-recorded-runs) gives reporting commands.
