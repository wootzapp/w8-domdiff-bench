# HTMLBench experiment in the Wootz task recorder

This branch compares the normal recorder with selected HTMLBench browser features. It uses the same Wootz browser image and does not change the Chromium source or ChromiumRL protocols.

The experiment changes the browser runtime environment. The normal `dom_model` and `dom_diff` capture path stays the same in both profiles.

## Changes to existing code

- `capture.py`: installs the selected audio/media and canvas scripts through CDP. They run on the current page and before later navigations.
- `task_cli.py`: adds `--htmlbench-profile`, prepares a separate browser container for that profile, and passes the choice to the runner.
- `runner.py`: passes the profile to capture and records the profile and prompt-size details in the run artifacts.
- `docker-compose.yml`: supports separate project names, containers, ports, fresh profiles, and profile-specific Chromium arguments.
- `tests/test_task_cli.py`: checks the environment-file command handling used by the repeated runs.

`capture.py` installs the page scripts with `Page.addScriptToEvaluateOnNewDocument` for future pages and `Runtime.evaluate` for the currently open page. It does not rewrite the website's HTML files.

Five profiles are available:

- `baseline`: normal recorder behavior.
- `images-disabled`: only disables image loading.
- `htmlbench-flags`: uses the applicable HTMLBench launch flags.
- `htmlbench-scripts`: uses the audio/media and canvas scripts.
- `htmlbench-full`: uses the flags and both scripts together.

The `htmlbench-full` profile adds these Chromium flags:

- `--disable-dev-shm-usage`
- `--ignore-gpu-blocklist`
- `--enable-webgl`
- `--use-angle=swiftshader`
- `--autoplay-policy=no-user-gesture-required`
- `--use-fake-ui-for-media-stream`
- `--blink-settings=imagesEnabled=false`

The runtime already uses `--no-sandbox` and `--disable-gpu`. The profile also adds two page scripts: one replaces audio with a silent version and makes media playback succeed; the other makes canvases focusable and focuses them automatically.

All profiles use the same `wootz-runtime:snapshot-diff` image, headed browser, and 1365×768 viewport. Separate containers and ports prevent the baseline and HTMLBench profiles from overwriting each other, and the browser profile is reset before each run.

## New files

- `htmlbench_profiles.py`: defines the baseline and HTMLBench profiles, flags, page scripts, ports, and manifest data.
- `configs/htmlbench_eval_tasks.json`: contains the four fixed evaluation tasks.
- `scripts/probe_htmlbench_profile.py`: checks that a selected profile is active in the browser.
- `scripts/run_htmlbench_trials.py`: runs the repeated baseline and HTMLBench comparisons.
- `scripts/summarize_htmlbench_eval.py`: reads run artifacts and produces the JSON and Markdown reports.
- `tests/test_htmlbench_profiles.py` and `tests/test_htmlbench_measurements.py`: test the profiles and measurements.
- `htmlbench-eval-runs/`: stores all 40 run artifacts and the generated reports.

## How the tasks were run

- Tasks: arXiv, GitHub/CPython, Hugging Face SQuAD, and OpenStreetMap cycling.
- Each task ran five times with `baseline` and five times with `htmlbench-full`.
- Total: 40 fresh runs.
- Repeating each task reduces the effect of normal model and action-path variation.
- Baseline and HTMLBench runs used the same task instructions, model setup, browser image, viewport, and DOM capture limits.
- The run order was interleaved so the same profile was not always tested first.
- The values below are medians from the five runs.
- Total tokens include every model response. DOM sizes count the initial state and each after-action state once.

## Token and file-size results

| Task | Total tokens: baseline → HTMLBench | `dom_model`: baseline → HTMLBench | `dom_diff`: baseline → HTMLBench |
|---|---:|---:|---:|
| GitHub/CPython | 109,348 → 89,940 (-17.75%) | 99,306 → 99,301 bytes (-0.005%) | 73,244 → 73,244 bytes (0%) |
| arXiv | 29,758 → 29,675 (-0.28%) | 18,744 → 18,776 bytes (+0.17%) | 102,982 → 102,982 bytes (0%) |
| Hugging Face SQuAD | 280,609 → 279,549 (-0.38%) | 270,957 → 270,955 bytes (-0.001%) | 4,043,180 → 4,043,180 bytes (0%) |
| OpenStreetMap cycling | 31,221 → 38,366 (+22.89%) | 18,294 → 19,864 bytes (+8.58%) | 34,734 → 39,811 bytes (+14.62%) |

## Result and observation

- The HTMLBench features did not consistently reduce tokens, `dom_model`, or `dom_diff` size.
- arXiv and Hugging Face were nearly unchanged in both tokens and DOM size.
- GitHub/CPython used fewer median tokens, but its DOM files stayed the same size. This means the token drop came from model/action variation, not DOM compression.
- OpenStreetMap became larger because its median recorded actions increased from 3 to 5, so more page states were captured.
- These features mainly change browser loading, rendering, audio/media behavior, and canvas focus. They do not change ChromiumRL snapshot selection or the code that creates `dom_model` and `dom_diff`.
