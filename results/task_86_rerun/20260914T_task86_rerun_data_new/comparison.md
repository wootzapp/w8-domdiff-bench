# browser_task_086-cross-endpoint-tide-station-inspection-20260914T091532Z verifier comparison

Frozen rubric SHA-256: `fb4c8bce0a8e20dfd3bf5838b788bee3eb643563bcc1244ad72ea94a9b686a37`  
Denominator: `15`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 14/15 (0.933) | False | 12 | 12 | 0 | 68,240 | 7,352 | 75,592 |
| DOM-model | 13/15 (0.867) | False | 17 | 17 | 0 | 76,097 | 11,535 | 87,632 |

DOM-model minus screenshot tokens: **+12,040 (+15.93%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use only NOAA station 9414290 and its details.self URL (or clearly report access failure) | 3 | 3 | 3 | 3 | 3 |
| Report base-station fields (ID, name, state, lat/long, timezone abbreviation & correction) | 4 | 3 | 2 | 3 | 3 |
| Follow details.self and report required linked-details fields | 5 | 5 | 5 | 5 | 5 |
| Respect task constraints on exactness and stopping condition | 3 | 3 | 3 | 3 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
