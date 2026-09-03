# Microsoft Screenshot vs. DOM-Model Verifier Report

This report compares the Microsoft screenshot verifier with the DOM-model verifier across 20 distinct evaluated tasks: task1–task16 and task34–task37. It uses the latest intended completed run for each task, keeps Microsoft as the fixed behavioral reference, and excludes superseded reruns from the aggregate denominator.

The available artifacts measure scores, outcomes, criterion agreement, calls, and tokens, but they do not contain independent human ground-truth labels. Therefore, “error rate” below means disagreement with Microsoft’s fixed baseline; it does not prove which verifier is objectively correct.

## Metric 1: Lower Error Rate and Higher Reliability

### Main finding

The current results do **not** establish that the DOM-model verifier has a lower error rate or higher reliability than the Microsoft screenshot baseline. DOM agrees with Microsoft on 17 of 20 binary outcomes (85%), but exact criterion-level agreement is 67 of 116 criteria (57.8%), and its mean absolute process-score difference is 22.1 percentage points.

| Reliability measure | Result | Interpretation |
|---|---:|---|
| Binary-outcome agreement | 17/20 (85.0%) | Both verifiers returned the same pass/fail outcome on 17 tasks. |
| Binary-outcome disagreement | 3/20 (15.0%) | DOM alone passed task9 and task12; Microsoft alone passed task8. |
| Cohen's kappa for binary outcome | 0.318 | Raw agreement is inflated by 16 tasks where both verifiers failed; chance-corrected agreement is modest. |
| Exact criterion agreement | 67/116 (57.8%) | The two modes assigned exactly the same final points on 67 criteria. |
| Criterion disagreement | 49/116 (42.2%) | Evidence representation or judge variance changed points on 49 criteria. |
| Exact task-level process-score agreement | 4/20 (20.0%) | Scores matched exactly on task3, task6, task7, and task14. |
| Process score within 10 percentage points | 9/20 (45.0%) | Eleven tasks differed by more than 10 points. |
| Mean absolute process-score difference | 22.1 percentage points | Typical baseline-relative score deviation is substantial. |
| Mean signed DOM-minus-Microsoft difference | +14.5 percentage points | DOM has an aggregate upward scoring bias relative to Microsoft. |
| DOM higher / equal / lower | 11 / 4 / 5 tasks | DOM over-scored relative to Microsoft more often than it under-scored. |

### Reliability conclusion

Using Microsoft as the fixed reference, the baseline-relative binary error/disagreement rate is **15%**, and binary reliability/agreement is **85%**. That 85% should not be presented alone: 16 of the 17 agreements are joint failures, producing a Cohen’s kappa of only **0.318**. The stronger criterion-level measure shows **42.2% disagreement**, so the evidence does not currently support a claim of higher DOM reliability.

A true error-rate comparison requires human labels for every criterion or a separately adjudicated gold score. With those labels, false-credit, missed-credit, precision, recall, and calibration error can be calculated independently for both evidence modes.

## Metric 2: Token Cost

### Main finding

Across the selected 20 runs, DOM-model scoring consumed **3,386,336 tokens**, compared with **2,699,727 tokens** for Microsoft screenshots. DOM therefore used **686,609 additional tokens**, an aggregate increase of **25.43%**.

| Cost measure | Microsoft screenshot | DOM model | Difference |
|---|---:|---:|---:|
| Total scoring tokens | 2,699,727 | 3,386,336 | +686,609 (+25.43%) |
| Mean tokens per task | 134,986 | 169,317 | +34,330 |
| Median tokens per task | 113,577 | 147,968 | +34,391 (+30.28%) |
| Logical LLM calls | 410 | 533 | +123 (+30.0%) |
| Tasks where modality was cheaper | 17/20 for screenshot | 3/20 for DOM | DOM cheaper on 15% of tasks |

Rubric-generation tokens are excluded from both columns because the same frozen rubric is generated once and scoring runs report `rubric_generation_calls: 0`. The three tasks where DOM used fewer scoring tokens were task2, task6, and task35.

## Per-Task Results

| Task and selected run | Microsoft score | DOM score | Score gap | Outcome | Microsoft tokens | DOM tokens | DOM token change |
|---|---:|---:|---:|---|---:|---:|---:|
| [task1 — 20260831T054814Z](/data/isha/msexecute/benchmarks-2/results/task1/20260831T054814Z/comparison.json) | 80.0% | 66.7% | −13.3 pp | Agree | 113,627 | 116,139 | +2.2% |
| [task2 — 20260829T152115Z](/data/isha/msexecute/benchmarks-2/results/task2/20260829T152115Z/comparison.json) | 55.0% | 65.0% | +10.0 pp | Agree | 180,312 | 163,442 | −9.4% |
| [task3 — 20260829T153037Z](/data/isha/msexecute/benchmarks-2/results/task3/20260829T153037Z/comparison.json) | 77.8% | 77.8% | 0.0 pp | Agree | 127,838 | 132,865 | +3.9% |
| [task4 — 20260829T153936Z](/data/isha/msexecute/benchmarks-2/results/task4/20260829T153936Z/comparison.json) | 55.6% | 72.2% | +16.7 pp | Agree | 69,340 | 76,709 | +10.6% |
| [task5 — 20260829T154829Z](/data/isha/msexecute/benchmarks-2/results/task5/20260829T154829Z/comparison.json) | 11.8% | 70.6% | +58.8 pp | Agree | 77,006 | 79,339 | +3.0% |
| [task6 — 20260829T155603Z](/data/isha/msexecute/benchmarks-2/results/task6/20260829T155603Z/comparison.json) | 42.9% | 42.9% | 0.0 pp | Agree | 174,208 | 162,111 | −6.9% |
| [task7 — 20260829T160213Z](/data/isha/msexecute/benchmarks-2/results/task7/20260829T160213Z/comparison.json) | 100.0% | 100.0% | 0.0 pp | Agree | 60,071 | 215,947 | +259.5% |
| [task8 — 20260829T160750Z](/data/isha/msexecute/benchmarks-2/results/task8/20260829T160750Z/comparison.json) | 92.3% | 73.1% | −19.2 pp | **Disagree** | 83,228 | 152,776 | +83.6% |
| [task9 — 20260829T161750Z](/data/isha/msexecute/benchmarks-2/results/task9/20260829T161750Z/comparison.json) | 30.0% | 90.0% | +60.0 pp | **Disagree** | 80,481 | 104,775 | +30.2% |
| [task10 — 20260829T162608Z](/data/isha/msexecute/benchmarks-2/results/task10/20260829T162608Z/comparison.json) | 57.1% | 85.7% | +28.6 pp | Agree | 65,254 | 87,944 | +34.8% |
| [task11 — 20260831T093943Z](/data/isha/msexecute/benchmarks-2/results/task11/20260831T093943Z/comparison.json) | 31.6% | 100.0% | +68.4 pp | Agree | 92,888 | 130,051 | +40.0% |
| [task12 — rerun-20260901-1](/data/isha/msexecute/benchmarks-2/results/task12/rerun-20260901-1/comparison.json) | 65.0% | 100.0% | +35.0 pp | **Disagree** | 84,496 | 110,368 | +30.6% |
| [task13 — rerun-20260901-1](/data/isha/msexecute/benchmarks-2/results/task13/rerun-20260901-1/comparison.json) | 45.0% | 50.0% | +5.0 pp | Agree | 329,601 | 453,608 | +37.6% |
| [task14 — 20260831T113823Z](/data/isha/msexecute/benchmarks-2/results/task14/20260831T113823Z/comparison.json) | 29.6% | 29.6% | 0.0 pp | Agree | 190,001 | 262,672 | +38.2% |
| [task15 — 20260827T075246Z](/data/isha/msexecute/benchmarks-2/results/task15/20260827T075246Z/comparison.json) | 39.3% | 48.2% | +8.9 pp | Agree | 95,225 | 113,224 | +18.9% |
| [task16 — 20260827T082503Z](/data/isha/msexecute/benchmarks-2/results/task16/20260827T082503Z/comparison.json) | 30.4% | 95.7% | +65.2 pp | Agree | 114,643 | 254,526 | +122.0% |
| [task34 — grounding rerun 3](/data/isha/msexecute/benchmarks-2/results/task34/20260827T_task34_grounding_rerun_3/comparison.json) | 75.0% | 58.3% | −16.7 pp | Agree | 113,526 | 143,159 | +26.1% |
| [task35 — 20260827T114546Z](/data/isha/msexecute/benchmarks-2/results/task35/20260827T114546Z/comparison.json) | 65.4% | 57.7% | −7.7 pp | Agree | 330,354 | 227,136 | −31.2% |
| [task36 — grounding rerun](/data/isha/msexecute/benchmarks-2/results/task36/20260827T_grounding_rerun/comparison.json) | 59.3% | 40.7% | −18.5 pp | Agree | 172,520 | 180,397 | +4.6% |
| [task37 — 20260827T_task37](/data/isha/msexecute/benchmarks-2/results/task37/20260827T_task37/comparison.json) | 68.2% | 77.3% | +9.1 pp | Agree | 145,108 | 219,148 | +51.0% |

## Evidence Status and Boundaries

Directly verified facts come from the selected `comparison.json` and normalized `run_metrics.json` artifacts: scores, outcomes, criteria, calls, retries, rubric hashes, and token totals. The aggregate includes one run per distinct task and excludes earlier superseded reruns.

The baseline-relative “error” interpretation is an inference: disagreement may arise from missing evidence, extra DOM evidence, final-state handling, evidence-selection behavior, or stochastic judge variation. Microsoft is the fixed experimental baseline, but it is not an independent gold label.

Run-to-run reliability remains unverified. Several tasks were rerun after rubric alignment, screenshot-state handling, or DOM grounding changes, so those repetitions are not controlled identical-condition trials and should not be pooled as stochastic-repeat measurements.

## Conclusion

The dominant pattern is that DOM is more expensive and often scores higher, while exact criterion agreement remains limited. The remaining risk is unsupported credit rather than demonstrated lower error. The next concrete experiment is a blinded human adjudication of all 116 criteria, followed by three identical-condition reruns per modality to measure true error and repeatability separately.
