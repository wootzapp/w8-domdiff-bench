# HTMLBench run results

4 tasks were run 5 times with `baseline` and 5 times with `htmlbench-full`. This produced 40 fresh runs. The table uses medians.

The tasks cover a document page, a dense repository page, an SPA, and an interactive map. Both profiles used the same browser image, viewport, task settings, and DOM capture limits.

Total tokens include every model response. DOM sizes count the initial state and each after-action state once.

| Task | Total tokens: baseline → HTMLBench | `dom_model`: baseline → HTMLBench | `dom_diff`: baseline → HTMLBench |
|---|---:|---:|---:|
| GitHub/CPython | 109,348 → 89,940 (-17.75%) | 99,306 → 99,301 bytes (-0.005%) | 73,244 → 73,244 bytes (0%) |
| arXiv | 29,758 → 29,675 (-0.28%) | 18,744 → 18,776 bytes (+0.17%) | 102,982 → 102,982 bytes (0%) |
| Hugging Face SQuAD | 280,609 → 279,549 (-0.38%) | 270,957 → 270,955 bytes (-0.001%) | 4,043,180 → 4,043,180 bytes (0%) |
| OpenStreetMap cycling | 31,221 → 38,366 (+22.89%) | 18,294 → 19,864 bytes (+8.58%) | 34,734 → 39,811 bytes (+14.62%) |

- There was no consistent reduction in token usage or DOM file size.
- 3 of 4 tasks had less than 1% DOM-size change.
- GitHub/CPython used fewer median tokens, but its DOM sizes stayed the same, so this was not DOM compression.
- OpenStreetMap cycling recorded 3 → 5 actions, which also increased the number of stored page states.
- The browser flags and page scripts changed runtime behavior, but not how ChromiumRL snapshots, `dom_model`, or `dom_diff` are created.
