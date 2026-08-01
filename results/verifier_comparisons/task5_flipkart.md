# Task5 Flipkart Verifier Comparison

## Task and fixed baseline

- Task ID: `task5`
- Instruction: “Go to Flipkart and add a blue color Adidas shoe to my cart.”
- Frozen rubric: `benchmarks/rubrics/task5_flipkart_canonical_rubric.json`
- Canonical runner input: `benchmarks/rubrics/task5_flipkart_canonical_task_data.tsv`
- Normalized rubric SHA-256: `35c2c8d89f793adbd0a9b96a4d82081ba22458fd1bd8fab8467b26d2faf2e47e`
- Maximum score: 10 points

All three verifier runs must use this exact frozen rubric:

1. Access Flipkart as the specified platform — 2 points
2. Find an Adidas shoe with blue color selected or clearly indicated — 4 points
3. Add the blue Adidas shoe to cart without checkout — 4 points

## Controlled comparison settings

| Setting | Fixed value |
|---|---|
| Main judge | `gpt-5.2` |
| Action and validity judge | `o4-mini` |
| Rubric threshold | 0.8 |
| Max evidence items per criterion | 5 |
| Keypoint threshold | 3 |
| Majority-vote instances | 1 |
| Top-level success criterion | Outcome |

Do not regenerate or modify the rubric between evidence modes. Rubric-generation calls must remain zero during all scoring runs.

## Comparison summary

| Evidence mode | Process score | Process pass | Outcome success | LLM calls | Total tokens | Status |
|---|---:|---:|---:|---:|---:|---|
| Screenshot | 6/10 (0.60) | False | False | 23 | 107,194 | Complete |
| DOM | 6/10 (0.60) | False | False | 40 | 276,988 | Complete |
| DOM-diff | 6/10 (0.60) | False | False | 25 | 165,701 | Complete |

## Screenshot-based verifier

### Run result

| Criterion | Action-only score | Final evidence score |
|---|---:|---:|
| Access Flipkart | 2/2 | 2/2 |
| Find a blue Adidas shoe | 2/4 | 4/4 |
| Add the shoe to cart | 0/4 | 0/4 |
| **Total** | **4/10** | **6/10** |

- Process score: **0.60**
- Rubric threshold pass: **False**
- Outcome success: **False**
- Task invalid: **False**
- Task ambiguity flag: **True** (`7.1`)
- Recorded actions: 9
- Source screenshots: 10
- Screenshots aligned and loaded by Microsoft’s verifier: 9
- Run duration: 61.09 seconds

The visual evidence corrected the second criterion from 2/4 to 4/4 because the product page explicitly showed an Adidas CyberRun shoe in blue. The final cart page contained no product, so the add-to-cart criterion remained 0/4 and outcome verification returned false.

### LLM calls

| Model | Calls |
|---|---:|
| GPT-5.2 | 20 |
| o4-mini | 3 |
| **Total** | **23** |

GPT-5.2 calls consisted of:

- 9 screenshot-relevance calls
- 6 screenshot-evidence calls
- 1 rubric reality-check call
- 2 rescoring/penalty calls
- 1 outcome-verification call
- 1 first-failure analysis call

o4-mini calls consisted of:

- 1 action-only rubric scoring call
- 1 trajectory-informed task-validity call
- 1 task-only validity/ambiguity call

Frozen-rubric generation calls during scoring: **0**.

### Token usage

| Model | Prompt tokens | Completion tokens | Reasoning tokens | Total tokens |
|---|---:|---:|---:|---:|
| GPT-5.2 | 83,185 | 5,421 | 0 | 88,606 |
| o4-mini | 15,706 | 2,882 | 1,920 | 18,588 |
| **Combined** | **98,891** | **8,303** | **1,920** | **107,194** |

Reasoning tokens are included within completion tokens and are not added again to total tokens.

### Artifacts

- Score: `outputs/screenshot_verify/task5_frozen_rubric/traj/task5/scores/mmrubric_0.8-5-3.json`
- Instrumented run metrics: `outputs/screenshot_verify/task5_frozen_rubric/run_metrics.json`
- Isolated scored trajectory: `outputs/screenshot_verify/task5_frozen_rubric/traj/task5/`

## DOM-based verifier

### Run result

| Criterion | Action-only score | Final DOM-evidence score |
|---|---:|---:|
| Access Flipkart | 2/2 | 2/2 |
| Find a blue Adidas shoe | 2/4 | 4/4 |
| Add the shoe to cart | 0/4 | 0/4 |
| **Total** | **4/10** | **6/10** |

- Process score: **0.60**
- Rubric threshold pass: **False**
- Outcome success: **False**
- Task invalid: **False**
- Task ambiguity flag: **True** (`7.1`)
- Recorded actions: 9
- Complete DOM evidence frames: 9
- Screenshot frames passed to this verifier: 0
- First failure: step 7
- Run duration: 102.22 seconds

The DOM evidence explicitly found the product heading `ADIDAS CyberRun M Running Shoes For Men (Blue , 6)`, raising the second criterion from 2/4 to 4/4. It also identified that step 7 targeted the “Bank offers” region rather than an Add-to-Cart control. Frames 8–9 reached `/viewcart` but contained “Missing Cart items?” and no cart line item, product title, or quantity. The add-to-cart criterion therefore remained 0/4 and outcome verification returned false.

This matches the screenshot verifier’s final 6/10 score and false outcome under the same frozen rubric.

### LLM calls

| Model | Calls |
|---|---:|
| GPT-5.2 | 36 |
| o4-mini | 4 |
| **Total** | **40** |

GPT-5.2 calls consisted of:

- 18 DOM-relevance calls;
- 13 selected-DOM-evidence analysis calls;
- 1 rubric reality-check call;
- 2 rescoring/penalty calls;
- 1 outcome-verification call;
- 1 first-failure analysis call.

o4-mini calls consisted of:

- 1 action-only rubric scoring call;
- 1 task-specific DOM-term generation call;
- 1 trajectory-informed task-validity call;
- 1 task-only validity/ambiguity call.

Frozen-rubric generation calls during scoring: **0**. All 40 logical calls produced 40 API attempts, so there were **0 retries**.

### Token usage

| Model | Prompt tokens | Completion tokens | Reasoning tokens | Total tokens |
|---|---:|---:|---:|---:|
| GPT-5.2 | 245,544 | 7,963 | 0 | 253,507 |
| o4-mini | 19,216 | 4,265 | 3,136 | 23,481 |
| **Combined** | **264,760** | **12,228** | **3,136** | **276,988** |

Reasoning tokens are included within completion tokens and are not added again to total tokens.

Compared with the screenshot run, full DOM used 17 more calls and 169,794 more tokens while producing the same score and outcome. This task’s full-DOM path analyzes before/after semantic state and transition evidence across all action-aligned frames; its token cost is therefore higher than the screenshot run for this trajectory.

### Artifacts

- Score: `outputs/dom_verify/task5_frozen_rubric/traj/task5/scores/mmrubric_0.8-5-3-dom-86f7f5d040e90042.json`
- Instrumented run metrics: `outputs/dom_verify/task5_frozen_rubric/run_metrics.json`
- Raw instrumentation: `outputs/dom_verify/task5_frozen_rubric/instrumentation.json`
- Isolated scored trajectory: `outputs/dom_verify/task5_frozen_rubric/traj/task5/`

## DOM-diff-only verifier

### Run result

| Criterion | Action-only score | Final DOM-diff score |
|---|---:|---:|
| Access Flipkart | 2/2 | 2/2 |
| Find a blue Adidas shoe | 2/4 | 2/4 |
| Add the shoe to cart | 2/4 | 2/4 |
| **Total** | **6/10** | **6/10** |

- Process score: **0.60**
- Rubric threshold pass: **False**
- Outcome success: **False**
- Task invalid: **False**
- Task ambiguity flag: **True** (`7.1`)
- Recorded actions: 9
- Complete DOM-diff frames: 9
- Screenshots, before/after DOM snapshots, page states, and verifier-action files passed: 0
- First failure: step 4
- Run duration: 89.12 seconds

The DOM-diff verifier confirmed Flipkart access and an Adidas product page. It could not recover the stable product heading that full DOM used to prove the selected product was blue, so the product criterion remained 2/4 instead of increasing to 4/4. It also could not observe the stable empty-cart text or absence of a line item. Because action history showed an attempted add-to-cart workflow and navigation to `/viewcart`, it retained partial cart credit at 2/4 instead of the 0/4 assigned by screenshot and full DOM evidence.

The 6/10 total therefore matches the other modes only numerically. Its criterion attribution is different and less conclusive: DOM-diff shifted two points from product-color verification to attempted cart completion. Outcome verification still correctly returned false because no diff proved that the required item was present in the cart.

### LLM calls

| Model | Calls |
|---|---:|
| GPT-5.2 | 21 |
| o4-mini | 4 |
| **Total** | **25** |

GPT-5.2 calls consisted of:

- 9 DOM-diff relevance calls;
- 7 selected-diff evidence-analysis calls;
- 1 rubric reality-check call;
- 2 rescoring/penalty calls;
- 1 outcome-verification call;
- 1 first-failure analysis call.

o4-mini calls consisted of:

- 1 action-only rubric scoring call;
- 1 task-specific DOM-term generation call;
- 1 trajectory-informed task-validity call;
- 1 task-only validity/ambiguity call.

Frozen-rubric generation calls during scoring: **0**. All 25 logical calls produced 25 API attempts, so there were **0 retries**.

### Token usage

| Model | Prompt tokens | Completion tokens | Reasoning tokens | Total tokens |
|---|---:|---:|---:|---:|
| GPT-5.2 | 136,611 | 5,689 | 0 | 142,300 |
| o4-mini | 18,894 | 4,507 | 3,392 | 23,401 |
| **Combined** | **155,505** | **10,196** | **3,392** | **165,701** |

Reasoning tokens are included within completion tokens and are not added again to total tokens.

Compared with full DOM, DOM-diff-only used 15 fewer calls and 111,287 fewer tokens. Compared with screenshots, it used 2 more calls and 58,507 more tokens.

### Artifacts

- Score: `outputs/dom_diff_verify/task5_frozen_rubric/traj/task5/scores/mmrubric_0.8-5-3-dom_diff-c00c01acfccdfba3.json`
- Instrumented run metrics: `outputs/dom_diff_verify/task5_frozen_rubric/run_metrics.json`
- Raw instrumentation: `outputs/dom_diff_verify/task5_frozen_rubric/instrumentation.json`
- Diff-only scored trajectory: `outputs/dom_diff_verify/task5_frozen_rubric/traj/task5/`

## Final comparison

All three modes used the identical frozen 10-point rubric and returned the same top-level result: process score 6/10, threshold failure, and outcome failure.

| Evidence mode | Access | Blue Adidas shoe | Added to cart | Total |
|---|---:|---:|---:|---:|
| Screenshot | 2/2 | 4/4 | 0/4 | 6/10 |
| Full DOM | 2/2 | 4/4 | 0/4 | 6/10 |
| DOM-diff only | 2/2 | 2/4 | 2/4 | 6/10 |

Screenshot and full DOM agreed at the criterion level. DOM-diff-only did not: transition-only evidence omitted stable product and cart state, so it could not prove blue color or empty-cart status. The equal total should therefore not be interpreted as equivalent evidence quality.

| Evidence mode | Calls | Total tokens |
|---|---:|---:|
| Screenshot | 23 | 107,194 |
| Full DOM | 40 | 276,988 |
| DOM-diff only | 25 | 165,701 |

For task5, screenshots were cheapest. DOM-diff-only was substantially cheaper than full DOM but still more expensive than screenshots, while losing criterion-level certainty about stable browser state.
