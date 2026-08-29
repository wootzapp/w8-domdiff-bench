# github-heavy-04-uv-installation-and-release-research-20260821T060958Z verifier comparison

Frozen rubric SHA-256: `8f72466823941c3434ec3985ba989477d16a7fee2f6e8f0784b1ce99ae077d76`  
Denominator: `23`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 7/23 (0.304) | False | 14 | 14 | 0 | 103,017 | 11,626 | 114,643 |
| DOM-model | 22/23 (0.957) | False | 17 | 17 | 0 | 240,890 | 13,636 | 254,526 |

DOM-model minus screenshot tokens: **+139,883 (+122.02%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use GitHub repository sources as evidence and tie each reported answer to a specific page/file | 4 | 4 | 2 | 2 | 4 |
| Report supported operating systems/platforms | 3 | 3 | 2 | 0 | 3 |
| Provide documented standalone installer command for Linux or macOS | 3 | 3 | 2 | 0 | 3 |
| Provide documented installer command for Windows | 3 | 3 | 2 | 0 | 3 |
| List package-manager installation alternatives shown in the README | 3 | 3 | 2 | 0 | 3 |
| Identify the latest stable release tag and publication date (exclude prereleases) | 3 | 3 | 3 | 3 | 3 |
| Report the repository license from the LICENSE file | 2 | 2 | 1 | 1 | 1 |
| Respect task constraints (no execution, no sign-in, no prereleases, no external snippet evidence) and stop after evidence-backed answers | 2 | 2 | 2 | 1 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
