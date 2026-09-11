# **Introducing w8-domdiff-bench**

We’re introducing a suite for recording and verifying browser-agent tasks, built on our custom Chromium browser. It brings together browser-native DOM capture, an agent execution harness, a paired trajectory dataset, and a DOM-based verifier. Together, these components make an agent’s actions and the evidence behind its answers available for inspection and evaluation.

We use [**Microsoft’s Universal Verifier**](https://www.microsoft.com/en-us/research/articles/the-art-of-building-verifiers-for-computer-use-agents/) **as the baseline** for our benchmark. It evaluates browser-agent trajectories from screenshots by generating a task-specific rubric, selecting relevant evidence, and assigning scores for each criterion, the process, and the outcome. We built our DOM-based verifier around the same evaluation design, replacing screenshot evidence with ordered Model DOM files from the same browser execution.

Both verifiers receive the exact same frozen rubric (including criteria, ordering, and maximum scores) and follow the same scoring pipeline. This comparison holds the agent’s actions and definition of success constant, allowing us to measure how the evidence format affects verification.

The [dataset](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks) contains 100 recorded browser tasks. In an initial audit of 44 tasks spanning 227 evaluation criteria, our DOM representation reduced evidence-loss cases from 14 to 6 compared with screenshots, **a 57% relative reduction.**

Browser-agent evaluation depends on what the recording preserves. A correct answer alone does not establish whether the agent visited the right page, applied the requested filter, or read the relevant information. Screenshots provide a visual record, but text can be clipped, URLs shortened, and control states difficult to distinguish. We built our browser infrastructure to capture these details explicitly and retain them throughout the agent’s execution.

That work began with detailed DOM captures and comparisons of page state before and after each action. These records preserved substantial detail, but individual raw captures and difference files could reach 20–80 MB. They also repeated page content across nested elements, making useful information difficult for a model to read efficiently.

We developed **DOMDiff**, a compact page representation that groups related information while removing unnecessary structure. Across 650 captured states, the readable DOMDiff averaged **4.84 KiB**, compared with 44.88 KiB for the detailed text view.

We then moved the selection and grouping logic into the browser itself. Our custom Chromium commands construct DOMDiff from the same structured snapshot retained in the recording. This gives us a common source for the detailed evidence and the compact representation supplied to the agent, and lets us trace omissions back to either page capture or content selection.

During a task, the harness supplies the model with DOMDiff, references to interactive controls, and context from previous actions. The model selects an action, the harness validates it, and `agent-browser` executes it in the Wootz browser. The resulting page becomes the next recorded state. Screenshots are saved alongside DOM evidence for later evaluation; the agent makes its decisions using text observations.

For verification, the recorded attempt passes through the screenshot baseline and our DOM-based verifier. Each identifies the states relevant to the shared rubric, analyzes the selected evidence, and scores the trajectory. Because both evaluate the same attempt, differences can be investigated against a common action history and final answer.

Our initial audit measures **evidence loss**: whether the recording preserves the information needed to judge a task criterion.

| Evidence format | Criteria with missing evidence | Evidence-loss rate |
| ----- | ----: | ----: |
| Screenshots : Microsoft Universal Verifier baseline | 14 / 227 | 6.2% |
| DOMDiff : our DOM-based verifier | 6 / 227 | 2.6% |

We manually audit missing evidence separately from verifier reasoning errors. These results measure evidence preservation across the audited tasks; they do not represent an agent success rate. 
Task based results are stored in:  
[https://github.com/wootzapp/wootzapp\_web\_browser-/blob/evidence-error-2/results.md](https://github.com/wootzapp/wootzapp_web_browser-/blob/evidence-error-2/results.md)

The suite gives researchers a shared record for running browser tasks, inspecting agent behavior through DOMDiff based verifier. 

Explore the [task dataset](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks), [and recording harness](https://github.com/wootzapp/wootzapp_web_browser-/tree/model-task-recorder). 
