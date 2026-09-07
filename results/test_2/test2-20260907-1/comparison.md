# browser_task_042-domain-registry-lookup-20260905T113946Z verifier comparison

Frozen rubric SHA-256: `86d9b1175542e1c3ca9add5a0913d05f76e6bc84f9ca4c936a717a8f9b0b33b4`  
Denominator: `16`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 16/16 (1.000) | True | 12 | 12 | 0 | 66,747 | 6,865 | 73,612 |
| DOM-model | 16/16 (1.000) | True | 28 | 28 | 0 | 107,682 | 12,216 | 119,898 |

DOM-model minus screenshot tokens: **+46,286 (+62.88%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access and use IANA Root Zone Database .museum delegation record page | 2 | 2 | 2 | 2 | 2 |
| Record top-level-domain type | 2 | 2 | 2 | 2 | 2 |
| Record sponsoring organization | 3 | 3 | 3 | 3 | 3 |
| Record registration date (not last-updated date) | 3 | 3 | 3 | 3 | 3 |
| Record WHOIS server | 2 | 2 | 2 | 2 | 2 |
| Record registration-services website | 2 | 2 | 2 | 2 | 2 |
| Respect constraints (no registration/contact; stop after five fields) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
