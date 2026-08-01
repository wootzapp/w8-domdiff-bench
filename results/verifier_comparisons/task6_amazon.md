# Task6 Amazon Verifier Comparison

## Task and fixed input rubric

- Task ID: `task6`
- Instruction: “go to amazon and add a blue color adidas shoe to my cart.”
- Frozen rubric: `benchmarks/rubrics/task6_amazon_canonical_rubric.json`
- Canonical runner input: `benchmarks/rubrics/task6_amazon_canonical_task_data.tsv`
- Frozen-rubric SHA-256: `dffae1031967b11d58ea0c1665596b35099cd2a28cda7c54cf817fae5ebbc6aa`
- Frozen input denominator: 10 points
- Judges: `gpt-5.2` and `o4-mini`

All modes receive the identical four-criterion frozen rubric. Microsoft’s runtime rubric reality check added a separate 2-point penalty criterion after inspecting the screenshot evidence, so the screenshot run’s scored denominator became 12. This runtime expansion is recorded explicitly and will be checked in the other modes.

## Comparison summary

| Evidence mode | Process score | Outcome | Calls | Tokens | Status |
|---|---:|---:|---:|---:|---|
| Screenshot | 9/12 (0.75) | False | 27 | 137,634 | Complete |
| Full DOM | 9/10 (0.90) | True | 46 | 316,243 | Complete |
| DOM-diff only | 9/10 (0.90) | True | 26 | 190,171 | Complete |

## Screenshot verifier

| Criterion | Action-only | Final evidence |
|---|---:|---:|
| Access Amazon | 2/2 | 2/2 |
| Locate an Adidas shoe product page | 1/2 | 1/2 |
| Verify/select a blue variant | 0/2 | 2/2 |
| Add the blue Adidas shoe to cart | 2/4 | 4/4 |
| Runtime penalty: extra quantity of 2 | 0/2 | 0/2 |
| **Total** | **5/12** | **9/12** |

- Process threshold pass: **False**
- Outcome success: **False**
- Actions: 11
- Screenshot references loaded: 11, backed by 10 unique image files
- Duration: 72.88 seconds
- Calls: GPT-5.2 24; o4-mini 3; total 27; retries 0
- Tokens: GPT-5.2 116,312; o4-mini 21,322; total 137,634
- Score: `outputs/screenshot_verify/task6_frozen_rubric/traj/task6/scores/mmrubric_0.8-5-3.json`
- Raw instrumentation: `outputs/screenshot_verify/task6_frozen_rubric/instrumentation.json`
- Run log: `outputs/screenshot_verify/task6_frozen_rubric/run.log`

The screenshots proved that the cart contained an Adidas shoe whose displayed color was `Dark Blue/White/Cyber Metallic`. They also showed quantity 2 and a two-item subtotal. The verifier therefore awarded the blue-variant and cart criteria fully, then added a new penalty criterion for the unsolicited second unit. Outcome verification returned false because the requested singular item was not left in the cart at quantity 1.

### Preserved unsuccessful attempt

Before the successful run, one screenshot attempt stopped after its initial o4-mini action-scoring call because the dataset exposed only 10 screenshot references for 11 actions. No GPT-5.2 evidence calls occurred. That attempt used 1 call and 8,967 tokens and is preserved at `outputs/screenshot_verify/task6_frozen_rubric_failed_alignment/`. The dataset now retains 10 unique files but supplies 11 action-aligned references by reusing the identical frame for the first two actions.


## Full-DOM verifier

| Criterion | Action-only | Final evidence |
|---|---:|---:|
| Access Amazon | 2/2 | 2/2 |
| Locate an Adidas shoe product page | 1/2 | 1/2 |
| Verify/select a blue variant | 0/2 | 2/2 |
| Add the blue Adidas shoe to cart | 0/4 | 4/4 |
| **Total** | **3/10** | **9/10** |

- Process threshold pass: **True**
- Outcome success: **True**
- Actions and complete DOM frames: 11
- Screenshot frames: 0
- Duration: 124.56 seconds
- Calls: GPT-5.2 42; o4-mini 4; total 46; retries 0
- Tokens: GPT-5.2 290,038; o4-mini 26,205; total 316,243
- Score: `outputs/dom_verify/task6_frozen_rubric/traj/task6/scores/mmrubric_0.8-5-3-dom-86f7f5d040e90042.json`
- Metrics: `outputs/dom_verify/task6_frozen_rubric/run_metrics.json`
- Run log: `outputs/dom_verify/task6_frozen_rubric/run.log`

The DOM evidence proved that the Amazon cart contained an Adidas shoe whose accessible text included a blue color name, so it awarded full color and cart credit. It did not add the screenshot run’s extra-quantity penalty, leaving the input denominator at 10 and returning outcome true. Consequently, this is not a strict denominator-matched result: the frozen rubric input was identical, but Microsoft’s evidence-dependent runtime reality check expanded only the screenshot rubric.


## DOM-diff-only verifier

| Criterion | Action-only | Final evidence |
|---|---:|---:|
| Access Amazon | 2/2 | 2/2 |
| Locate an Adidas shoe product page | 1/2 | 1/2 |
| Verify/select a blue variant | 0/2 | 2/2 |
| Add the blue Adidas shoe to cart | 0/4 | 4/4 |
| **Total** | **3/10** | **9/10** |

- Process threshold pass: **True**
- Outcome success: **True**
- Actions and aligned DOM-diff frames: 11
- Screenshots, before/after DOM snapshots, page states, and verifier-action files passed: 0
- Duration: 82.95 seconds
- Calls: GPT-5.2 22; o4-mini 4; total 26; retries 0
- Tokens: GPT-5.2 165,001; o4-mini 25,170; total 190,171
- Score: `outputs/dom_diff_verify/task6_frozen_rubric/traj/task6/scores/mmrubric_0.8-5-3-dom_diff-c00c01acfccdfba3.json`
- Metrics: `outputs/dom_diff_verify/task6_frozen_rubric/run_metrics.json`
- Run log: `outputs/dom_diff_verify/task6_frozen_rubric/run.log`

The diffs included an `Item Added` transition and cart text naming `adidas Men's Gamecourt 2 M, Dark Blue/White/Cyber Metallic, 9.5`, which was enough for full color and cart credit. Although a later diff exposed cart count 2, the outcome judge treated that as possibly including a pre-existing item. It therefore did not infer the unwanted second-unit side effect that screenshots visibly established.

## Final comparison

| Evidence mode | Frozen criteria earned | Runtime penalty | Scored total | Outcome | Calls | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| Screenshot | 9/10 | 0/2 extra-quantity penalty | 9/12 | False | 27 | 137,634 |
| Full DOM | 9/10 | Not added | 9/10 | True | 46 | 316,243 |
| DOM-diff only | 9/10 | Not added | 9/10 | True | 26 | 190,171 |

**Strict comparison validation:** failed because the runtime denominators differ (`12`, `10`, `10`). All other core controls checked here—task ID, 11-action alignment, frozen-rubric hash, model roles, and input dataset structure—match.

The three modes agree on all four frozen criteria: each ultimately awards 9/10, with the only lost point coming from not opening a dedicated Adidas product page. They disagree on the side effect. Screenshots clearly show quantity 2 for the same shoe and a two-item subtotal, causing the runtime reality check to add a penalty and the outcome judge to fail the task. Full DOM and DOM-diff prove that a blue Adidas shoe is present but do not ground that quantity interpretation strongly enough; both return success.

Therefore, this run is a valid comparison of what each evidence mode allowed the unchanged verifier pipeline to infer, but it is not a strict fixed-denominator comparison after Step 5. The input rubric, hash, actions, and settings were identical; the Microsoft reality-check stage itself changed the screenshot rubric based on visual evidence. For a mathematically fixed baseline, compare the four frozen criteria separately (all are 9/10) and report the runtime side-effect penalty independently, as above.

### Token comparison

- Full DOM used 178,609 more tokens than screenshots and 126,072 more than DOM-diff.
- DOM-diff used 52,537 more tokens than screenshots.
- Across the three successful scoring runs: 99 calls and 644,048 tokens.
- Including the preserved failed screenshot alignment attempt: 100 calls and 653,015 tokens.
