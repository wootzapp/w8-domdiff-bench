# Day 1 Learning Log — Microsoft Universal Verifier

## Experiment objective

Execute Microsoft's released Universal Verifier from the pinned `microsoft/fara`
repository against at least one frozen CUAVerifierBench trajectory. This is an
end-to-end execution smoke test.

## Log

### 2026-07-21 — Experiment initialized

- Read the complete Day 1 execution brief (`day1_execute_ms_universal_verifier.md`).
- Created the prescribed `ms-paper-execution/` workspace layout.
- The top-level workspace contains an empty `.git` directory, so it is not an
  initialized Git repository. Reproducibility for this experiment will instead
  be recorded through the required Fara commit file, exact command log, package
  freeze, system information, manifests, and logs.
- Next: clone and pin Microsoft Fara, then create the Python environment.

### 2026-07-21 — Repository pinned and input contract verified

- Cloned `https://github.com/microsoft/fara.git` and checked out the required
  detached commit `9f14b6e34094fe469a54a821e81e013a0739520d`.
- Inspected the pinned `webeval/README.md` before implementing materialization.
  The materializer must emit newline-delimited JSON in `web_surfer.log` and a
  complete `FinalAnswer` payload; the brief's shortened final-answer example is
  not sufficient for a robust run.
- The installed interpreter is Python 3.12.3, satisfying Fara's `>=3.10`
  requirement and the brief's Python 3.12 recommendation.

### 2026-07-21 — Environment installation finding

- `pip install -e .` for Fara completed successfully.
- The unmodified `pip install -e ./webeval` did not complete and left neither
  `webeval` nor its Torch/vLLM packages installed. Its dependency metadata pulls
  the full Fara solver stack (Torch, CUDA libraries, vLLM), while the official
  `verify_trajectories.py` standalone entry point explicitly skips the solver.
- Planned, documented deviation: install the official `webeval` package
  editable with `--no-deps`, then install only dependencies reached by the
  official standalone verifier. No verifier code will be replaced or modified.

### 2026-07-21 — Import smoke test passed

- Installed the official `webeval` package editable with `--no-deps`, then
  installed the frozen-dataset client (`datasets`) and the verifier's missing
  runtime import (`tiktoken`).
- The actual standalone-runner imports passed: `fara`, `Trajectory`, and
  `MMRubricAgent` all import successfully.
- The brief's exact smoke snippet imports `VerifierAgent`, but that name is not
  exported by this pinned Fara revision. This is a brief/revision mismatch, not
  a blocker: `verify_trajectories.py` imports only `MMRubricAgent` and its
  related result/configuration types.

### 2026-07-21 — Frozen dataset downloaded and task selected

- Downloaded CUAVerifierBench to the workspace-local cache. The target split
  has 106 trajectories; two local Arrow shards were produced.
- The `datasets` client attempted a network metadata refresh on subsequent
  loads despite the completed local cache. The experiment scripts now load the
  immutable local Arrow shards directly, avoiding that nondeterministic
  dependency.
- Chosen initial smoke-test task: dataset index 1, `Adidas--11857213`, because
  it has only 11 screenshots. No human labels, verifier outputs, metrics, or
  reviewer annotations were accessed for selection.
- The selected row has a string, newline-delimited structured action log, 11
  RGB PNG screenshots (1440×900), a non-aborted final answer, and an empty
  `init_url`. The empty URL is faithfully preserved in `tasks.json`.

### 2026-07-21 — Materialization and validation passed

- Materialized `Adidas--11857213` using an explicit allow-list. The copied
  inputs are limited to task metadata, instruction, initial URL, action log,
  screenshots, final answer, and aborted status; no labels or prior verifier
  outputs were copied.
- `Trajectory.from_folder()` loaded the folder successfully. It parsed 10
  actions, and all 11 PNG screenshots open successfully. The record includes
  one extra final screenshot; the released `shared_data_adapter` deliberately
  aligns and uses only the first screenshot per parsed action.
- The official `verify_trajectories.py --help` command runs successfully.

### 2026-07-21 — Judge preflight blocked by released config and identity

- The pinned repository includes `gpt-4o` and `o4-mini` Azure AD development
  config templates, not the brief's example `gpt-5.2` configuration. They were
  combined without editing their contents for the official runner.
- Both minimal requests reached client construction but failed at Azure AD token
  acquisition. This environment has no Azure CLI login, usable managed identity,
  or configured workload/environment credential.
- The released template endpoints are placeholders, so a real endpoint config
  and matching credential source are also required before a score can be
  generated. Sanitized preflight results were saved; no secret was stored.

### 2026-07-21 — Official verifier attempt and Day 1 partial result

- Ran the official `webeval/scripts/verify_trajectories.py` entry point with
  one process and one materialized trajectory. It loaded the OM2W task data,
  found the trajectory, constructed one `o4-mini` and one `gpt-4o` client, and
  entered rubric generation.
- The official verifier made five rubric-generation retries, each blocked by
  `ClientAuthenticationError` during Azure AD token acquisition. The generated
  report row has `status: "error"`, runtime 5.42 seconds, and no score path.
- No `mmrubric_*.json` was produced. Therefore this is correctly classified as
  Day 1 **partial success**, not an end-to-end execution of the paper.
- Final artifact integrity passed: all required partial-success artifacts exist,
  all JSON/JSONL files parse, experiment scripts compile, and the command log
  has valid shell syntax.

## Resume requirement

To complete the Day 1 success criterion, provide a non-placeholder endpoint
configuration directory containing a multimodal judge and an action/rubric
judge, plus a usable credential method (for example an authenticated Azure CLI
session, managed identity with deployment access, or approved environment-based
credentials). Then rerun the exact official command recorded in
`ms-paper-execution/commands/day0_smoke_test.sh`; a real `mmrubric_*.json` must be
created before claiming end-to-end execution.

### 2026-07-21 — OpenAI-only retry prepared

- Created an OpenAI-only endpoint config using `gpt-4o` for both judge roles.
  It intentionally contains no `api_key` field: the released OpenAI wrapper
  delegates authentication to the `OPENAI_API_KEY` environment variable.
- Added `.env` patterns to the experiment `.gitignore` as a safeguard.
- The API key exported in the user's Cursor terminal is not inherited by this
  agent's execution environment. Its value was not read, printed, or saved.

### 2026-07-21 — OpenAI preflight and end-to-end verifier success

- A local ignored `.env` file was used only to inject `OPENAI_API_KEY` into
  short-lived child processes. The key was not read into logs or artifacts.
- The official `GracefulRetryClient` preflight succeeded for both a text-only
  and image-bearing `gpt-4o` request.
- The released `verify_trajectories.py` ran against the one frozen trajectory
  and produced `scores/mmrubric_0.8-5-3.json`. The process verdict passed with
  10.0/11.0 points (0.9091), while the outcome verdict was false (top-level
  score 0); an unsuccessful task outcome is still a successful verifier run.
- The next official invocation detected the existing score as cached, which
  confirms the first OpenAI invocation completed the scoring write.

### 2026-07-21 — Final Day 1 smoke-test status

- Confirmed the saved official score JSON at
  `ms-paper-execution/results/day0_smoke_test/scores/mmrubric_0.8-5-3.json` and copied it
  from the trajectory's `scores/` directory into the Day 0 artifact bundle.
- Final verifier result: process rubric success (`10.0/11.0 = 0.9091`), outcome
  success `false`, top-level outcome score `0`, first failure step `1`.
- The OpenAI-backed Day 1 execution goal is complete: the released verifier
  code consumed a real frozen trajectory and generated a real Universal
  Verifier score file. This remains a one-trajectory smoke test, not a full
  benchmark reproduction.

### 2026-07-22 — Full-run programme scaffolded

- Preserved the completed Day 1 smoke-test paths and added a stage-based project
  layout for the full-split execution.
- Created the frozen E0 configuration for all 106 `fara7b_om2w_browserbase`
  trajectories, including the label-safe input allow-list and the documented
  local model substitution (`gpt-4o` for both verifier roles).
- Created the run state file with E0 marked
  `setup_complete_waiting_for_validation`.
- This was structure-only work. No full-run trajectory was materialized, no
  judge-model call was made, and no benchmark label or metric was accessed.

### 2026-07-22 — E0 setup completed; execution remains blocked

- Added a machine-readable experiment registry for E0 with
  `run_authorized: false`.
- Added `scripts/experiment_guard.py`; its validation test correctly refused
  E0 because setup validation and explicit user authorization have not yet been
  recorded.
- No execution, trajectory materialization, human-label access, metric
  calculation, or background job was started during this setup work.

### 2026-07-23 - Scope cleanup

- User cancelled all later ablation and benchmark-reporting work.
- Removed the obsolete future-phase configuration and planning files.
- The repo now retains Day 0 smoke-test artifacts and Day 1 full-trajectory
  execution artifacts only.
