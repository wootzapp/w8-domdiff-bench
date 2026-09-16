# **Introducing w8-domdiff-bench**

w8-domdiff-bench is a benchmark and evaluation suite for building more capable browser agents. Built on w8-core, our custom Chromium-based browser engine, it combines structured page observations, recorded trajectories, and DOM-based verification to turn browser interactions into useful feedback for model development.

We used [**Microsoft’s Universal Verifier**](https://www.microsoft.com/en-us/research/articles/the-art-of-building-verifiers-for-computer-use-agents/) **as the baseline** for our benchmark. It evaluates browser-agent trajectories from screenshots by generating a task-specific rubric, selecting relevant evidence, and assigning scores for each criterion, the process, and the outcome. We built our DOM-based verifier around the same evaluation design, replacing screenshot evidence with ordered DOM-diff Optimized files from the same browser execution.

Both verifiers receive the exact same frozen rubric (including criteria, ordering, and maximum scores) and follow the same scoring pipeline. This comparison holds the agent’s actions and definition of success constant, allowing us to measure how the evidence format affects verification.

The [dataset](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks) contains 100 recorded browser tasks. Across all 100 reruns and 639 evaluation criteria, our DOM representation reduced evidence-loss cases from 26 to 2 compared with screenshots, **a 92% relative reduction.**

Browser-agent evaluation depends on what the recording preserves. A correct answer alone does not establish whether the agent visited the right page, applied the requested filter, or read the relevant information. Screenshots provide a visual record, but text can be clipped, URLs shortened, and control states difficult to distinguish. We built our browser infrastructure to capture these details explicitly and retain them throughout the agent’s execution.

Our browser infrastructure evolved from detailed DOM capture into **DOM-diff Optimized**, a compact representation refined to preserve the evidence needed for agent decisions and verification.

| Stage | What we built or improved | Why it mattered |
| --- | --- | --- |
| **DOM capture** | Captured page text, attributes, element paths, styles, and layout geometry. | Established a detailed record of browser state beyond screenshots. |
| **DOM-diff** | Compared page states before and after each action to record what changed. | Connected actions to their effects, but raw captures and diff files could reach **20–80 MB**, with substantial repetition. |
| **DOM-diff Optimized** | Combined DOM, accessibility, and layout information into grouped content, tables, media descriptions, controls, and scroll regions. | Reduced repetition while keeping related facts together. Across 650 states, its readable text averaged **4.84 KiB**, versus **44.88 KiB** for the detailed text view. |
| **Browser-native processing** | Moved DOM-diff Optimized selection and grouping into the browser, using the same captured snapshot as the detailed record. | Kept the compact view grounded in recorded page state. The recorder also moved to one live observation per state, without separate diff files. |
| **Evidence-preservation refinements** | Improved child-text selection, retained repeated facts belonging to different results, preserved complete author labels and selected-control states, and corrected visibility handling after scrolling. | Addressed omissions in capture and formatting that could hide useful evidence. |
| **Subtree-text limit removal** | Removed the subtree-text limit that truncated text within nested page elements. | Further improved evidence preservation; reported development measurements showed DOM evidence loss dropping from **26% to 0.4%**. |

The **26% → 0.4%** figures describe development measurements. The final 100-task rerun below reports **2 missing criteria out of 639 (0.3%)**; these are presented separately because the development measurement's task and criterion counts are not specified.

During a task, the harness supplies the model with DOM-diff Optimized, references to interactive controls, and context from previous actions. The model selects an action, the harness validates it, and `agent-browser` executes it in the Wootz browser. The resulting page becomes the next recorded state. Screenshots are saved alongside DOM evidence for later evaluation; the agent makes its decisions using text observations.

For verification, the recorded attempt passes through the screenshot baseline and our DOM-based verifier. Each identifies the states relevant to the shared rubric, analyzes the selected evidence, and scores the trajectory. Because both evaluate the same attempt, differences can be investigated against a common action history and final answer.

Our initial audit measures **evidence loss**: whether the recording preserves the information needed to judge a task criterion.

| Evidence format | Criteria with missing evidence | Evidence-loss rate |
| ----- | ----: | ----: |
| Screenshots: Microsoft Universal Verifier baseline | 26 / 639 | 4.1% |
| DOM-diff Optimized: our DOM-based verifier | 2 / 639 | 0.3% |

We manually audit missing evidence separately from verifier reasoning errors. These results measure evidence preservation across the audited tasks; they do not represent an agent success rate.

The final rerun outputs are stored under `results/task_01_rerun/` through `results/task_100_rerun/`. Each task retains the screenshot-verifier result, DOM-verifier result, and consolidated comparison JSON.
