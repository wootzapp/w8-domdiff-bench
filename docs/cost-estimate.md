# Cost estimates

Amounts are **estimated from list prices and explicit usage assumptions**, not measured spend. Each trial covers all 40 tasks in both arms: 80 independently evaluated recordings. The primary profile is used unless a Pro comparison is explicitly selected. No generation or countTokens request was used to estimate costs.

| Stage | Model | Delivery | Input / output USD per million |
| --- | --- | --- | --- |
| Browser actions | gemini-3.8-flash | Normal | 0.75 / 3.75 through 2026-12-31; 1.50 / 7.50 afterward |
| Native screenshot and DOM verifiers | gemini-3.5-flash-lite | Batch | 0.15 / 1.25 |
| Common completion and audit adjudication | gpt-6.1-sol | Batch | 1 / 5 up to 272,000 input tokens; 2 / 7.50 above |
| Audit inventory; optional Pro native profile | gemini-3.1-pro-preview | Batch | 1 / 6 up to 200,000 input tokens; 2 / 9 above |
| Rubric generation and dependency check | gpt-5.2 | Normal | 1.75 / 14 |

Rates follow the [Google price table](https://aistudio.google.com/docs/pricing) and [OpenAI price table](https://developers.openai.com/api/docs/pricing.md). Batch discounts apply only to the recorded Batch items. Cached input is a subset of input; thinking/reasoning is a subset of output. Unknown usage prevents an exact cost total. Runtime receipts price calls individually using their transport and model; they do not add reasoning tokens twice.

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
| actor dom | $7.72 | $12.29 | $16.81 |
| actor screenshot | $6.25 | $9.95 | $13.61 |
| paired completion | $22.19 | $39.25 | $52.24 |
| audit inventory | $31.67 | $44.75 | $62.20 |
| audit adjudication | $27.82 | $45.89 | $58.88 |
| native screenshot | $16.30 | $22.43 | $27.94 |
| native dom | $17.73 | $24.33 | $30.18 |
| google | $79.67 | $113.75 | $150.74 |
| openai | $50.01 | $85.14 | $111.13 |
| total | $129.68 | $198.89 | $261.87 |

For any positive k: **k × $129.68–$261.87**, with a central planning figure of **k × $198.89**. Rubric generation is approximately **$2.38 once for all 40 tasks**, not once per trial. Actor spending in these estimates doubles after the introductory price expires; judge rates are unchanged in that scenario.

## Usage assumptions

Let T be actor turns per arm, N=T+1 states, C criteria, H=120T action-history tokens, D=2,800 DOM tokens/state and I=1,500 image tokens/state. The image value is an unmeasured planning allowance; provider receipts determine actual image usage. Actor requests assume 4,100 input +650 output tokens per DOM turn and 3,200 input +550 output per screenshot turn. Output includes thinking.

For each native verifier in each actor run:

| Stage group | Calls | Input per call | Output per call |
| --- | --- | --- | --- |
| Action-only and two validity stages | 3 | 2,000+H+180C | 1,200 |
| Relevance | N | 2,000+180C+P | 100+50C |
| Selected-state analysis | U=min(N,5C) | 2,500+H+P+900C/U | 1,750C/U |
| Summary global checks | 4 | 4,000+H+800C | 1,000+150C |
| Raw-evidence global checks | 2 | 4,000+H+800C+min(UP,85,000) | 1,000+150C |

P is I for the screenshot verifier and D for the DOM verifier. These are cost assumptions, not runtime limits or new selection rules. Both full native pipelines run on every recording. Conditional/failure work and overlapping selected states can change actual counts. Existing top-five selection and single-instance voting remain unchanged.

Each recording has one common completion call: input N(D+I)+H+7,000+180C, output 1,000+200C. Inventory has one call: input N(D+I)+H+8,000+2,000C, output 1,000+600C. Adjudication has one call: input N(D+I)+H+9,000+3,100C, output 1,000+650C. Rubrics assume two calls per task, together 10,000 input and 3,000 output tokens. Long-context price tiers are evaluated per request.

The native input guard stays at 115,000 tokens; the 85,000 figure above is an evidence allowance in the estimate, not an added runtime cap. Full completion/audit requests are never truncated by the Batch scheduler. Live context fit and judge agreement remain gated checks.

## Pro pilot comparison

The comparison adds the Pro native verifier calls and a separate inventory/adjudication for each existing pilot recording. It shares common completion and does not repeat actor work or rubric preparation. These additional requests are excluded from the primary forty-task totals. The comparison report accounts for each profile and shared completion separately.
