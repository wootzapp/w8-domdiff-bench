# browser_task_060-discography-chronology-20260909T084002Z verifier comparison

Frozen rubric SHA-256: `cd27cd3e128211e168513b2ec40fd1ad5174ff28626caad1b4176c6432d59dcd`  
Denominator: `18`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 5/18 (0.278) | False | 12 | 12 | 0 | 78,264 | 8,834 | 87,098 |
| DOM-model | 4.5/18 (0.250) | False | 14 | 14 | 0 | 96,371 | 12,050 | 108,421 |

DOM-model minus screenshot tokens: **+21,323 (+24.48%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use correct source scope: Daft Punk MusicBrainz artist page → official release groups → Album section only (or clearly report inability to access it) | 3 | 3 | 3 | 3 | 3 |
| Correctly identify the first three qualifying dated Album entries in displayed chronological order (or explain why this cannot be determined) | 4 | 1 | 0 | 1 | 0 |
| Entry #1: Open release-group page and report title + release-group 'First release date' as shown (including partial dates if that is all MusicBrainz provides) | 3 | 3 | 3 | 1 | 1.5 |
| Entry #2: Open release-group page and report title + release-group 'First release date' as shown (including partial dates if that is all MusicBrainz provides) | 3 | 0 | 0 | 0 | 0 |
| Entry #3: Open release-group page and report title + release-group 'First release date' as shown (including partial dates if that is all MusicBrainz provides) | 3 | 0 | 0 | 0 | 0 |
| Stopping condition and exclusion rules followed (as far as the site allows determination) | 2 | 0 | 0 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
