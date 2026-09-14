# Evidence Error Audit: Task 100

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Event title and coordinates | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Did You Feel It? community MMI | Yes / No | Yes / Yes | 1/2 / 2/2 | SCREENSHOT_MISSED_DOM_CAUGHT |
| ShakeMap MMI | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Landslide estimate | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Liquefaction estimate | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Origin fields | Yes / Yes | Yes / Yes | 4/5 / 4/5 | BOTH_CAUGHT |

The second-pass visual check confirms a large red `IX` badge in `screenshot0.png`. The screenshot verifier incorrectly said no readable MMI value was visible, while the DOM verifier cited `Did You Feel It? IX mmi`. This is a confirmed screenshot perception/grounding miss. All other criterion evidence is available and recovered in both modalities.
