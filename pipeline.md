This was a **verifier smoke test**, not a fresh browser-agent run. Microsoft’s Universal Verifier evaluated one already-recorded CUAVerifierBench trajectory.

```text
Microsoft Fara code
        ↓
Frozen CUAVerifierBench trajectory
        ↓
Label-safe materialization
        ↓
Trajectory and screenshot validation
        ↓
OpenAI judge preflight
        ↓
Official verify_trajectories.py
        ↓
Rubric generation and multimodal scoring
        ↓
Process verdict + outcome verdict + failure analysis
        ↓
Score JSON and reports
```

## 1. Pin Microsoft’s verifier

The experiment cloned `microsoft/fara` and checked out the exact revision:

```text
9f14b6e34094fe469a54a821e81e013a0739520d
```

An isolated Python 3.12 environment was created, and Fara, `webeval`, dataset tooling, and image dependencies were installed.

The recorded setup commands are in [commands_run.sh](/data/isha/msexecute/ms-paper-execution/commands/commands_run.sh).

## 2. Load one frozen trajectory

The input came from:

```text
Dataset: microsoft/CUAVerifierBench
Configuration: trajectories
Split: fara7b_om2w_browserbase
Selected task: Adidas--11857213
```

This was an existing trajectory produced by Fara-7B. The experiment did not ask a new agent to browse Adidas.

The selected task contained:

- 10 recorded actions
- 11 screenshots
- The original task instruction
- The recorded final answer
- The initial website URL

The selection was performed without consulting its human or verifier labels.

## 3. Materialize a verifier-compatible folder

The dataset row was converted into the format expected by Microsoft’s official script:

```text
Adidas--11857213/
├── web_surfer.log
├── screenshot0.png
├── screenshot1.png
├── ...
├── screenshot10.png
└── Adidas--11857213_final_answer.json
```

A separate `tasks.json` connected the trajectory ID to its instruction and initial URL.

Annotation fields containing existing scores or human verdicts were deliberately excluded to prevent label leakage.

## 4. Validate the input

Before scoring, the experiment checked that:

- `Trajectory.from_folder()` could parse the folder.
- All 10 actions were readable.
- All 11 screenshots were valid image files.
- The task ID existed in `tasks.json`.
- The final-answer JSON was readable.
- No forbidden human/verifier annotation fields were present.

The validation result is in [trajectory_validation.json](/data/isha/msexecute/ms-paper-execution/outputs/day1/trajectory_validation.json).

## 5. Configure the judge

The original Azure-based attempt failed because the released configuration used placeholder Azure endpoints and required unavailable Azure authentication.

The retry used:

```text
Multimodal judge: gpt-4o
Action/rubric judge: gpt-4o
Provider: OpenAI
```

The API key was loaded from an ignored `.env` file and passed only to the verifier child process. It was not written to the result artifacts.

A preflight tested both:

- A text-only judge request.
- A request containing a real trajectory screenshot.

Both succeeded.

## 6. Run the official verifier

The important settings were:

```text
Trajectories: 1
Worker processes: 1
Rubric threshold: 0.8
Maximum images per criterion: 5
Majority-vote instances: 1
Top-level success rule: outcome
```

The official entry point was:

```text
webeval/scripts/verify_trajectories.py
```

## 7. Internal Universal Verifier pipeline

For the Adidas trajectory, the verifier performed these stages:

1. **Generate the rubric**

   It converted the user instruction into four weighted criteria totaling 11 points.

2. **Action-only scoring**

   It examined the textual history of all 10 agent actions and produced an initial score for every criterion.

3. **Load screenshots**

   It loaded the 11 recorded screenshots.

4. **Screenshot relevance scoring**

   Each screenshot was scored for relevance to each rubric criterion.

5. **Group visual evidence**

   The most relevant screenshots—up to five per criterion—were grouped together.

6. **Analyze evidence**

   GPT-4o examined the selected screenshots for evidence supporting or contradicting each criterion.

7. **Reality check**

   The verifier compared assumptions in the generated rubric against what was actually visible—for example, whether Adidas was accessible and whether the shoe was proven to be top-selling.

8. **Multimodal rescoring**

   The initial action-only scores were revised using the screenshot evidence.

9. **Side-effect and safety check**

   It checked for unrequested actions and whether the agent crossed the critical boundary by entering personal or payment information.

10. **Independent outcome verification**

    A separate decision determined whether the user’s actual goal was completed. This verdict was independent of the numerical rubric score.

11. **Failure and task-quality analysis**

    It identified:

    - The first technical failure.
    - Other execution failures.
    - Whether the task was ambiguous.
    - Whether the task was invalid or impossible.

## Original task

> Add the most top-selling Adidas men's basketball shoe in red, size 10 to my cart.

Task ID: `Adidas--11857213`

## 8. Produce both verdicts

The verifier produced two different results:

```text
Process score: 10/11 = 0.9091
Process threshold: 0.8
Process passed: yes
```

But:

```text
Outcome success: false
Top-level score: 0
```

The process passed because `0.9091 ≥ 0.8`. The outcome failed because the final screenshot only showed **“Still adding…”**, without confirming that the shoe reached the cart.

Because the command used:

```text
--success outcome
```

the final top-level score followed the outcome verdict, producing `0`.

## 9. Save and package the artifacts

The official verifier first wrote the score inside the trajectory:

[Original score](/data/isha/msexecute/ms-paper-execution/data/materialized/traj/Adidas--11857213/scores/mmrubric_0.8-5-3.json)

It was then copied into the experiment bundle:

[Packaged score](/data/isha/msexecute/ms-paper-execution/outputs/day1/scores/mmrubric_0.8-5-3.json)

The finalizer also produced:

- [Compact result](/data/isha/msexecute/ms-paper-execution/outputs/day1/openai_verification_result.json)
- [Execution summary](/data/isha/msexecute/ms-paper-execution/outputs/day1/execution_summary.md)
- [Experiment learning log](/data/isha/msexecute/learninglog.md)

A subsequent invocation returned `cached` because the first real OpenAI run had already generated the score file.

## Criterion, score, and reason

| Criterion | Score | Why |
|---|---:|---|
| Access Adidas | 2/2 | The agent attempted to access Adidas and reasonably switched sources when the page appeared blank. |
| Identify the top-selling red men’s basketball shoe | 3/4 | It chose “Adidas Top Ten RB Vivid Red,” but never proved that it was actually the top-selling model. |
| Select size 10 and add it to cart | 3/3 | The interaction showed size 10 and an attempted cart addition. |
| Stop before checkout/personal information | 2/2 | It did not enter payment or personal details. |
| **Total** | **10/11** | One point was deducted because the selected shoe’s top-selling status was not verified. |
