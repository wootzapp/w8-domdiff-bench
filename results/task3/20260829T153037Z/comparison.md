# viewport-modern-3-software-release-research-20260829T074724Z verifier comparison

Frozen rubric SHA-256: `5fd39f2558fe7db4286f211ce92d185171d7ea648b004a8ed7c55f8c0bcb7db1`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 14/18 (0.778) | False | 20 | 20 | 0 | 117,763 | 10,075 | 127,838 |
| DOM-model | 14/18 (0.778) | False | 22 | 22 | 0 | 122,093 | 10,772 | 132,865 |

DOM-model minus screenshot tokens: **+5,027 (+3.93%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Navigate to Microsoft Playwright GitHub Releases page (no sign-in) | 3 | 3 | 3 | 3 | 3 |
| Identify newest non-preview release and record metadata | 4 | 4 | 4 | 2 | 2 |
| Extract three changes from the release notes | 4 | 4 | 4 | 4 | 4 |
| Verify one reported change using official Playwright documentation | 4 | 4 | 4 | 2 | 2 |
| Respect constraints and stopping condition | 3 | 3 | 3 | 3 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
