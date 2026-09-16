# **Introducing w8-domdiff-bench**

w8-domdiff-bench is a benchmark and evaluation suite for building more capable browser agents. Built on w8-core, our custom Chromium-based browser engine, it combines structured page observations, recorded trajectories, and DOM-based verification to turn browser interactions into useful feedback for model development.

We used [**Microsoft’s Universal Verifier**](https://www.microsoft.com/en-us/research/articles/the-art-of-building-verifiers-for-computer-use-agents/) **as the baseline** for our benchmark. It evaluates browser-agent trajectories from screenshots by generating a task-specific rubric, selecting relevant evidence, and assigning scores for each criterion, the process, and the outcome. We built our DOM-based verifier around the same evaluation design, replacing screenshot evidence with ordered Model DOM files from the same browser execution.

Both verifiers receive the exact same frozen rubric (including criteria, ordering, and maximum scores) and follow the same scoring pipeline. This comparison holds the agent’s actions and definition of success constant, allowing us to measure how the evidence format affects verification.

The [dataset](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks) contains 100 recorded browser tasks. Across all 100 reruns and 639 evaluation criteria, our DOM representation reduced evidence-loss cases from 26 to 2 compared with screenshots, **a 92% relative reduction.**

Browser-agent evaluation depends on what the recording preserves. A correct answer alone does not establish whether the agent visited the right page, applied the requested filter, or read the relevant information. Screenshots provide a visual record, but text can be clipped, URLs shortened, and control states difficult to distinguish. We built our browser infrastructure to capture these details explicitly and retain them throughout the agent’s execution.

That work began with detailed DOM captures and comparisons of page state before and after each action. These records preserved substantial detail, but individual raw captures and difference files could reach 20–80 MB. They also repeated page content across nested elements, making useful information difficult for a model to read efficiently.

We developed **DOMDiff**, a compact page representation that groups related information while removing unnecessary structure. Across 650 captured states, the readable DOMDiff averaged **4.84 KiB**, compared with 44.88 KiB for the detailed text view.

We then moved the selection and grouping logic into the browser itself. Our custom Chromium commands construct DOMDiff from the same structured snapshot retained in the recording. This gives us a common source for the detailed evidence and the compact representation supplied to the agent, and lets us trace omissions back to either page capture or content selection.

During a task, the harness supplies the model with DOMDiff, references to interactive controls, and context from previous actions. The model selects an action, the harness validates it, and `agent-browser` executes it in the Wootz browser. The resulting page becomes the next recorded state. Screenshots are saved alongside DOM evidence for later evaluation; the agent makes its decisions using text observations.

For verification, the recorded attempt passes through the screenshot baseline and our DOM-based verifier. Each identifies the states relevant to the shared rubric, analyzes the selected evidence, and scores the trajectory. Because both evaluate the same attempt, differences can be investigated against a common action history and final answer.

Our initial audit measures **evidence loss**: whether the recording preserves the information needed to judge a task criterion.

| Evidence format | Criteria with missing evidence | Evidence-loss rate |
| ----- | ----: | ----: |
| Screenshots: Microsoft Universal Verifier baseline | 26 / 639 | 4.1% |
| DOMDiff: our DOM-based verifier | 2 / 639 | 0.3% |

We manually audit missing evidence separately from verifier reasoning errors. These results measure evidence preservation across the audited tasks; they do not represent an agent success rate.

The final rerun outputs are stored under `results/task_01_rerun/` through `results/task_100_rerun/`. Each task retains the screenshot-verifier result, DOM-verifier result, and consolidated comparison JSON.
