# HTMLCure evaluation in the Wootz task recorder

This branch tests whether usable features from the official HTMLCure/HTMLBench release can reduce task tokens, `dom_model`, `dom_diff`, turns, or improve verifier evidence in the Wootz recorder. It uses the pinned official HTMLCure commit `18d68e8f1e5c2bcef7f3c00bcab3147e2a99d4db`.

The Chromium source and ChromiumRL protocols were not changed. The experiment changes browser startup/page behavior and runs official HTMLCure analysis after the recorder has saved its normal evidence.

## What was added

Three new treatments were compared:

- `htmlcure-helper`: the exact official interaction helper, using the normal headed Wootz runtime.
- `htmlcure-headed`: official extra Chromium flags, page-safety script, and interaction helper, still headed.
- `htmlcure-runtime`: the same official features with Wootz headless mode and the official 1280×720 viewport.

The first two official launch flags, `--no-sandbox` and `--disable-gpu`, are already supplied by the Wootz runtime. The remaining flags come from official `htmleval/concurrency/browser_pool.py`. Wootz still has its own normal startup flags, so `htmlcure-runtime` is a Wootz reproduction of the HTMLCure settings, not the Playwright browser process itself.

The exact official code used was:

- `htmleval/core/page_safety.py`: silent `AudioContext` and successful media `play()`.
- `htmleval/phases/extract.py`: canvas focus and interaction helper.
- `static_analysis/analyzer.py`: HTML static analysis.
- `render_test/renderer.py` and `probes.py`: generic rendering and interaction probes.
- `core/screenshot.py`: Playwright screenshot path and direct CDP fallback.
- `frame_types.py` and `keyframe_selector.py`: SSIM changes and keyframe selection.
- `test_runner/schema.py`, `actions.py`, and `executor.py`: four generic page-health cases.

The official helper normally appears near the end of generated HTML. For live websites, a small adapter waits for `DOMContentLoaded` and then runs the unchanged official JavaScript. The post-run is separate from task recording, so its clicks, keys, screenshots, and page mutations cannot change what the agent already saw.

The reusable feature task reads its local smoke-page address from `HTMLCURE_FIXTURE_URL`; recorded manifests keep the actual URL used.

## Changed and new files

Existing files changed:

- `htmlbench_profiles.py`: loads official flags/scripts and defines the three treatments.
- `docker-compose.yml`: accepts separate headless and Chromium window-size settings.
- `configs/htmlbench_eval_tasks.json`: points to four frozen, self-contained normal task files.
- `scripts/run_htmlbench_trials.py`: runs exactly two repetitions, resumes finished slots, runs the official post-run, and limits a post-run to 150 seconds.
- `scripts/summarize_htmlbench_eval.py`: measures tokens, calls, turns, DOM sizes, stored bytes, and official evidence separately.
- `tests/test_htmlbench_profiles.py`, `tests/test_htmlbench_measurements.py`, and `tests/test_htmlbench_trials.py`: check profiles and measurements.

New files:

- `scripts/run_official_htmlcure_postrun.py`: runs the official static analysis, RenderTest, screenshots/CDP fallback, keyframes, and generic test actions.
- `scripts/serve_official_htmlcure_fixture.py`: serves the exact `_SMOKE_HTML` page from official `htmleval/__main__.py`.
- `configs/tasks/*.json`: four normal browsing tasks and one separately labelled HTMLCure feature task.
- `configs/htmlcure_feature_tasks.json`: contains only the official canvas/keyboard feature task.
- `htmlbench-eval-runs/htmlcure-complete-summary.json`: complete machine-readable measurements.

## How the tasks were run

- Normal tasks: arXiv, GitHub/CPython, Hugging Face SQuAD, and OpenStreetMap cycling.
- Normal total: 4 tasks × 3 treatments × 2 repetitions = 24 runs.
- Feature task: the official HTMLCure animated canvas/keyboard smoke page.
- Feature total: 1 task × 3 treatments × 2 repetitions = 6 runs.
- Final total: 30 runs, with exactly `r1` and `r2` for every task/profile pair.
- The existing five-run baseline and earlier `htmlbench-full` results were reused as comparison data.

Baseline medians from the earlier five-run study:

| Task | Tokens | `dom_model` bytes | `dom_diff` bytes |
|---|---:|---:|---:|
| arXiv | 29,758 | 18,744 | 102,982 |
| GitHub/CPython | 109,348 | 99,306 | 73,244 |
| Hugging Face | 280,609 | 270,957 | 4,043,180 |
| OpenStreetMap | 31,221 | 18,294 | 34,734 |

Exact new results (`r1 / r2`):

| Task | Treatment | Tokens | `dom_model` bytes | `dom_diff` bytes |
|---|---|---:|---:|---:|
| arXiv | helper | 29,622 / 29,737 | 18,740 / 18,742 | 102,982 / 102,982 |
| arXiv | headed | 29,627 / 29,714 | 18,776 / 18,774 | 102,982 / 102,982 |
| arXiv | runtime | 31,392 / 31,495 | 21,659 / 21,659 | 103,480 / 103,480 |
| GitHub | helper | 90,336 / 75,890 | 99,295 / 69,495 | 73,244 / 47,367 |
| GitHub | headed | 236,099 / 73,296 | 123,710 / 70,031 | 99,124 / 47,367 |
| GitHub | runtime | 130,328 / 164,143 | 71,650 / 71,594 | 46,323 / 46,323 |
| Hugging Face | helper | 349,653 / 348,865 | 272,878 / 270,929 | 4,045,739 / 4,043,150 |
| Hugging Face | headed | 349,470 / 349,811 | 272,869 / 272,870 | 4,045,739 / 4,045,739 |
| Hugging Face | runtime | 498,585 / 282,031 | 412,858 / 275,861 | 4,063,808 / 4,045,702 |
| OpenStreetMap | helper | 47,088 / 47,053 | 31,052 / 31,052 | 44,262 / 44,262 |
| OpenStreetMap | headed | 35,238 / 43,712 | 16,970 / 23,134 | 38,982 / 44,056 |
| OpenStreetMap | runtime | 34,448 / 39,975 | 17,495 / 17,427 | 39,161 / 38,970 |
| Official canvas task | helper | 19,375 / 19,149 | 2,391 / 2,391 | 22,205 / 22,205 |
| Official canvas task | headed | 65,803 / 31,758 | 3,189 / 2,392 | 31,101 / 22,221 |
| Official canvas task | runtime | 21,025 / 19,315 | 2,392 / 2,390 | 22,221 / 22,189 |

The GitHub runs did not all save the same number of page states, so their smaller file values are not treated as compression evidence.

## Evidence result

HTMLCure produced extra text summaries, keyframes, screenshots, state variables, and generic pass/fail data. This evidence was not sent to the task agent, so it could not reduce the task's token use.

| Task | Official text evidence | Does it preserve the task facts? |
|---|---|---|
| arXiv | 1,043 characters | Yes. It contains `v1`, `v7`, and both exact dates. |
| GitHub | 836–844 characters | No. It mainly contains navigation/file-list text, not all requested YAML fields. |
| Hugging Face | 528–562 characters | No. Reloading the page produced a login view without the split counts. |
| OpenStreetMap | 384 characters | No. It shows `Loading...`, not the route distance and time. |
| Official canvas task | 16 characters plus `game_vars` and received keys | Yes for score/key state, although the generic deep-gameplay probe timed out in every post-run. |

The generic cases passed even when task-specific facts were missing. They are useful page-health evidence, but they cannot replace `dom_model`/`dom_diff` or a task-specific verifier. Keyframe PNGs also added roughly 82 KB to 2.93 MB per run, so they increased stored evidence size.

## Overall result

- No tested HTMLCure feature consistently reduced tokens, model calls, turns, `dom_model`, or `dom_diff`.
- arXiv helper/headed results were almost identical to baseline.
- Hugging Face used about 24–39% more median tokens than baseline.
- OpenStreetMap used about 19–51% more median tokens and usually stored more DOM evidence because it took more actions.
- The GitHub results had unequal completed page-state counts, so they did not show a reliable reduction.
- The official canvas helper worked for its own small canvas page, but that result does not transfer to document, SPA, repository, or map tasks.
- HTMLCure's post-run can add useful supplementary evidence, especially for simple static pages and canvas state, but it is not a smaller or reliably complete replacement for the recorder's evidence.
