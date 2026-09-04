# browser_task_057-clinical-trial-filtering-20260902T210409Z verifier comparison

Frozen rubric SHA-256: `479289d7d032e7abdc8d46509686bb8e09396b60bef1f2e8ea52f54458cf7265`  
Denominator: `22`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 5/22 (0.227) | False | 44 | 44 | 0 | 248,840 | 21,139 | 269,979 |
| DOM-model | 5.5/22 (0.250) | False | 53 | 53 | 0 | 368,371 | 30,855 | 399,226 |

DOM-model minus screenshot tokens: **+129,247 (+47.87%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access ClinicalTrials.gov and run search for the term "type 2 diabetes" | 2 | 2 | 2 | 2 | 2 |
| Apply required filters (Recruiting, Phase 3, United States) | 4 | 2 | 4 | 2 | 2 |
| Sort results by Last Update Posted (newest first) | 2 | 1 | 2 | 0 | 0.5 |
| Report result #1 (topmost displayed after filters + newest-first sort) | 4 | 0 | 4 | 0 | 0 |
| Report result #2 (second displayed after filters + newest-first sort) | 4 | 0 | 4 | 0 | 0 |
| Report result #3 (third displayed after filters + newest-first sort) | 4 | 0 | 4 | 0 | 0 |
| Follow task constraints and stopping condition | 2 | 1 | 2 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
