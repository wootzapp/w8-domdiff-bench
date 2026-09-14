# browser_task_042-domain-registry-lookup-20260909T081023Z verifier comparison

Frozen rubric SHA-256: `44708721e982b01a34e3cbe39681e8a0cce591c3ea119bb299b4d51cb5019375`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 15/15 (1.000) | True | 12 | 12 | 0 | 65,194 | 5,568 | 70,762 |
| DOM-model | 15/15 (1.000) | True | 25 | 25 | 0 | 94,023 | 13,501 | 107,524 |

DOM-model minus screenshot tokens: **+36,762 (+51.95%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use IANA Root Zone Database .museum delegation page | 2 | 2 | 2 | 2 | 2 |
| Record TLD type | 2 | 2 | 2 | 2 | 2 |
| Record sponsoring organization | 2 | 2 | 2 | 2 | 2 |
| Record registration date (not last updated) | 3 | 3 | 1 | 3 | 3 |
| Record WHOIS server | 2 | 2 | 2 | 2 | 2 |
| Record registration services website | 2 | 2 | 2 | 2 | 2 |
| Respect constraints and stopping condition | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
