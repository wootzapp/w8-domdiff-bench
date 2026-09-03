# viewport-modern-17-booking-com-amsterdam-hotel-comparison-20260829T082728Z verifier comparison

Frozen rubric SHA-256: `b74caab594233a08f97850a6bccc96ced676755f505f447885876601023bd98d`  
Denominator: `30`  
Rubric generation calls during scoring: `0` for both modes

| Mode | Process score | Outcome | Calls | Attempts | Retries | Prompt | Completion | Total |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| Microsoft screenshots | 12/30 (0.400) | False | 63 | 63 | 0 | 358,425 | 25,139 | 383,564 |
| DOM-model | 9/30 (0.300) | False | 70 | 70 | 0 | 430,872 | 34,879 | 465,751 |

DOM-model minus screenshot tokens: **+82,187 (+21.43%)**.

## Criterion attribution

| Criterion | Max | Screenshot action | DOM-model action | Screenshot final | DOM-model final |
|---|---:|---:|---:|---:|---:|
| Search parameters set on Booking.com | 4 | 4 | 4 | 4 | 4 |
| Apply required visible filters (rating and budget) where available | 4 | 2 | 2 | 2 | 2 |
| Open and review Hotel 1 that qualifies (or best available if none qualify) | 5 | 5 | 5 | 2 | 1 |
| Open and review Hotel 2 that qualifies (or best available if none qualify) | 5 | 5 | 5 | 2 | 1 |
| Open and review Hotel 3 that qualifies (or best available if none qualify) | 5 | 5 | 5 | 2 | 1 |
| Compare the three hotels on required dimensions | 4 | 4 | 4 | 0 | 0 |
| Recommend one hotel without booking | 3 | 3 | 3 | 0 | 0 |

## Interpretation checks

- Equal scores are not treated as proof that the two modalities contain equivalent evidence.
- Pixel-only facts remain unsupported by DOM-model evidence unless explicitly encoded.
- Phase A generation usage is reported separately from both scoring totals.
- Reasoning tokens are included in completion tokens and are not added twice.
