# browser_task_008-software-release-research-20260909T072902Z verifier comparison

Frozen rubric SHA-256: `dbd97e8cc89d447ae6e4e451a73e26b3eacff43e05f39ea4d84a8ce8e496ffa0`  
Denominator: `17`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 13/17 (0.765) | False | 23 | 23 | 0 | 122,055 | 11,193 | 133,248 |
| DOM-model | 14.5/17 (0.853) | False | 36 | 36 | 0 | 183,566 | 18,865 | 202,431 |

DOM-model minus screenshot tokens: **+69,183 (+51.92%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Playwright GitHub Releases page (or reasonable official fallback) without signing in | 2 | 2 | 2 | 2 | 2 |
| Identify the newest non-preview (non-pre-release) release | 2 | 2 | 2 | 2 | 1.5 |
| Record release metadata (tag and publication date) for the identified stable release | 3 | 1 | 1 | 1 | 1 |
| Extract three distinct changes from the release notes of that stable release | 4 | 0 | 0 | 2 | 4 |
| Verify one of the listed changes using official Playwright documentation | 4 | 4 | 4 | 4 | 4 |
| Comply with constraints and stopping condition | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
