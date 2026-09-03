# viewport-modern-18-google-flights-nonstop-fare-comparison-20260829T083137Z verifier comparison

Frozen rubric SHA-256: `9fd0ab24b20e4163c3995125d78e1d071b39b449459e1429a07477fc4287c820`  
Denominator: `20`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 7/20 (0.350) | False | 27 | 27 | 0 | 142,807 | 11,248 | 154,055 |
| DOM-model | 17/20 (0.850) | False | 30 | 30 | 0 | 218,810 | 14,539 | 233,349 |

DOM-model minus screenshot tokens: **+79,294 (+51.47%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Use Google Flights to run the specified search (route, dates, passengers, cabin) or clearly report access issues | 4 | 4 | 4 | 3 | 4 |
| Apply the nonstop filter (direct flights only) or clearly report inability to do so | 3 | 3 | 3 | 0 | 3 |
| Identify and compare the lowest-priced visible nonstop options (up to three) given available results | 4 | 0 | 4 | 1 | 4 |
| Report required details for each compared option (airline, departure time, duration, round-trip fare) or clearly note missing fields | 6 | 0 | 3 | 2 | 3 |
| Recommend the best balance of price and schedule (no booking) | 3 | 0 | 3 | 1 | 3 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
