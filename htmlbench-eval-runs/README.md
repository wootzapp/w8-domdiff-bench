# HTMLCure evaluation runs

This folder stores the recorded Wootz tasks and official HTMLCure post-run evidence. The final dataset contains exactly two runs (`r1` and `r2`) for every task/profile pair.

## What is stored where

The final 30-run evaluation is stored in three folders:

- `htmlcure-helper/`: exact official interaction helper, headed Wootz.
- `htmlcure-headed/`: official flags, page safety, and helper, headed Wootz.
- `htmlcure-runtime/`: the same treatment in Wootz headless 1280×720 mode.

Earlier comparison data is kept separately:

- `baseline/`: the earlier five-run normal-recorder reference.
- `htmlbench-full/`: the earlier five-run flags/scripts treatment.

`report.md` and `report.json` summarize the earlier baseline-versus-`htmlbench-full` study. `htmlcure-complete-summary.json` combines those measurements with the final 30-run evaluation.

Normal browsing tasks are stored under `arxiv-static/`, `github-dense/`, `huggingface-spa/`, and `openstreetmap-canvas/`. The separate official feature task is stored under `htmlcure-canvas-keyboard/`; its page is the exact `_SMOKE_HTML` from the pinned official HTMLCure repository.

The reusable feature task takes its local page URL from `HTMLCURE_FIXTURE_URL`, while each recorded manifest keeps the actual fixture URL used in that run.

Each run directory contains the normal recorder files such as `manifest.json`, `decisions.jsonl`, `initial/`, and `steps/`. Its `htmlcure_official/` folder contains:

- `static_analysis.json`
- `render_test.json`
- `test_runner.json`
- `summary.json`
- selected frames and `direct_cdp_capture.png`

Official post-run files are measured separately and are excluded from `stored_run_bytes`, so they do not make the normal recorder look artificially larger.

## Run count

- Four normal tasks × three profiles × two repetitions = 24 runs.
- One official feature task × three profiles × two repetitions = 6 runs.
- Final two-repeat dataset = 30 runs.
- All 30 have a completed official `summary.json`.

## Features tested

- Official HTMLCure Chromium flags for software WebGL, autoplay, fake media permission UI, disabled images, and reduced shared-memory use. Wootz already supplied `--no-sandbox` and `--disable-gpu`.
- Official page-safety script, which replaces `AudioContext` with silent audio and makes media `play()` return success.
- Complete official interaction helper: canvas focus, keyboard/click/drag helpers, mutation tracking, error tracking, and `window.__probe` state snapshots.
- Headed Wootz behavior and the HTMLCure-style headless 1280×720 runtime.
- Official static HTML analysis and the RenderTest interaction probe registry.
- Official Playwright screenshot path, direct CDP screenshot fallback, SSIM frame comparison, and keyframe selection.
- Official generic test-runner actions and the exact official canvas/keyboard smoke page.

The official analysis ran after each normal recorder task was saved. This kept its extra interactions and screenshots separate from the evidence and token usage seen by the task agent.

## Median result from the two new runs

| Task | Profile | Tokens | `dom_model` bytes | `dom_diff` bytes |
|---|---|---:|---:|---:|
| arXiv | helper | 29,680 | 18,741 | 102,982 |
| arXiv | headed | 29,671 | 18,775 | 102,982 |
| arXiv | runtime | 31,444 | 21,659 | 103,480 |
| GitHub | helper | 83,113 | 84,395 | 60,306 |
| GitHub | headed | 154,698 | 96,871 | 73,246 |
| GitHub | runtime | 147,236 | 71,622 | 46,323 |
| Hugging Face | helper | 349,259 | 271,904 | 4,044,445 |
| Hugging Face | headed | 349,641 | 272,870 | 4,045,739 |
| Hugging Face | runtime | 390,308 | 344,360 | 4,054,755 |
| OpenStreetMap | helper | 47,071 | 31,052 | 44,262 |
| OpenStreetMap | headed | 39,475 | 20,052 | 41,519 |
| OpenStreetMap | runtime | 37,212 | 17,461 | 39,066 |
| Official canvas | helper | 19,262 | 2,391 | 22,205 |
| Official canvas | headed | 48,781 | 2,791 | 26,661 |
| Official canvas | runtime | 20,170 | 2,391 | 22,205 |

The GitHub runs did not all save the same number of page states, so their smaller values are not compression evidence. Complete per-run values are in `HTMLBENCH_EVAL.md` and `htmlcure-complete-summary.json`.

## Main observation

- HTMLCure browser flags and page scripts do not change the ChromiumRL snapshot or `dom_model`/`dom_diff` generation code.
- No treatment consistently reduced tokens, turns, or DOM size on the normal tasks.
- Official post-run text preserved the arXiv facts and canvas score/state, but it missed the required GitHub YAML fields, Hugging Face split counts, and OpenStreetMap route values.
- Generic HTMLCure tests can pass while task-specific evidence is missing.
- Official screenshots/keyframes add evidence, but also add about 82 KB to 2.93 MB per run.
