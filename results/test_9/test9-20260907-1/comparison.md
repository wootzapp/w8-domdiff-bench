# browser_task_057-clinical-trial-filtering-20260907T084356Z verifier comparison

Frozen rubric SHA-256: `479289d7d032e7abdc8d46509686bb8e09396b60bef1f2e8ea52f54458cf7265`  
Denominator: `22`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 8/22 (0.364) | False | 41 | 41 | 0 | 243,401 | 22,053 | 265,454 |
| DOM-model | 12/22 (0.545) | False | 51 | 51 | 0 | 338,988 | 32,563 | 371,551 |

DOM-model minus screenshot tokens: **+106,097 (+39.97%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access ClinicalTrials.gov and run search for the term "type 2 diabetes" | 2 | 2 | 2 | 2 | 2 |
| Apply required filters (Recruiting, Phase 3, United States) | 4 | 4 | 4 | 2 | 3 |
| Sort results by Last Update Posted (newest first) | 2 | 2 | 2 | 0 | 1 |
| Report result #1 (topmost displayed after filters + newest-first sort) | 4 | 0 | 2 | 2 | 2 |
| Report result #2 (second displayed after filters + newest-first sort) | 4 | 0 | 2 | 1 | 1.5 |
| Report result #3 (third displayed after filters + newest-first sort) | 4 | 0 | 2 | 0 | 1.5 |
| Follow task constraints and stopping condition | 2 | 2 | 2 | 1 | 1 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
