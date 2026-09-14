# browser_task_007-cross-site-recipe-lookup-20260909T072810Z verifier comparison

Frozen rubric SHA-256: `92aa9a35c900cfea9df77683c49e2d406af0a68c5cafd9169458a5c81323c15b`  
Denominator: `12`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12/12 (1.000) | True | 12 | 12 | 0 | 71,091 | 7,567 | 78,658 |
| DOM-model | 12/12 (1.000) | True | 25 | 25 | 0 | 106,954 | 15,287 | 122,241 |

DOM-model minus screenshot tokens: **+43,583 (+55.41%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Access Amazon India Grocery & Gourmet Foods bestsellers list (or report block) | 2 | 2 | 0 | 2 | 2 |
| Verify and record the item ranked #2 in Amazon India Grocery & Gourmet Foods bestsellers | 2 | 2 | 0 | 2 | 2 |
| Access AllRecipes and locate a recipe that uses the identified ingredient (or report access/search failure) | 3 | 3 | 3 | 3 | 3 |
| Report the AllRecipes recipe title | 1 | 1 | 1 | 1 | 1 |
| Report the full ingredient list from the AllRecipes recipe | 2 | 2 | 2 | 2 | 2 |
| Comply with constraints (no sign-in, no cart, no purchase; stop on bot check) | 2 | 2 | 2 | 2 | 2 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
