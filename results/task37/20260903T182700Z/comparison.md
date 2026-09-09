# browser_task_042-domain-registry-lookup-20260902T195301Z verifier comparison

Frozen rubric SHA-256: `86d9b1175542e1c3ca9add5a0913d05f76e6bc84f9ca4c936a717a8f9b0b33b4`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12/16 (0.750) | False | 45 | 45 | 0 | 217,901 | 14,771 | 232,672 |
| DOM-model | 8/16 (0.500) | False | 61 | 61 | 0 | 219,055 | 24,632 | 243,687 |

DOM-model minus screenshot tokens: **+11,015 (+4.73%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access and use IANA Root Zone Database .museum delegation record page | 2 | 2 | 2 | 2 | 2 |
| Record top-level-domain type | 2 | 0 | 2 | 1.5 | 1.5 |
| Record sponsoring organization | 3 | 0 | 3 | 3 | 3 |
| Record registration date (not last-updated date) | 3 | 0 | 3 | 0 | 0 |
| Record WHOIS server | 2 | 0 | 2 | 2 | 0 |
| Record registration-services website | 2 | 0 | 2 | 2 | 0 |
| Respect constraints (no registration/contact; stop after five fields) | 2 | 2 | 2 | 1.5 | 1.5 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
