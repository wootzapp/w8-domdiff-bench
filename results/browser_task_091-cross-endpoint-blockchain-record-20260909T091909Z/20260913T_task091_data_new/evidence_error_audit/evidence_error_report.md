# Evidence Error Audit: Task 91

| Criterion | Screenshot present/caught | DOM present/caught | SS / DOM | Classification |
|---|---|---|---:|---|
| Resolve height 800000 to its block hash | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Construct the documented block URL | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Retrieve the exact block record | Yes / Yes | Yes / Yes | 2/2 / 2/2 | BOTH_CAUGHT |
| Report all requested block fields | Yes / Yes | Yes / Yes | 8/8 / 8/8 | BOTH_CAUGHT |
| Preserve hashes, timestamp, size, and weight | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |
| Stop after the requested output | Yes / Yes | Yes / Yes | 3/3 / 3/3 | BOTH_CAUGHT |

Second-pass source review confirmed the hash in `screenshot0.png`/`dom_model0.txt` and the complete block record in `screenshot1.png`/`dom_model1.txt`. No source loss or verifier miss was found.
