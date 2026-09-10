## **DOM-Based vs. Screenshot-Based Evidence for Verifying Agent Trajectories**

**Claim**

Our claim is that DOM-based evidence is better than screenshot-based evidence for verifying an agent's browser trajectory, especially for tasks that depend on text, URLs, form values, controls, and browser state. We are testing whether the DOM preserves more of the information required by the verifier and therefore reduces evidence loss.

For this experiment, we took Microsoft's \[[Universal Verifier](https://www.microsoft.com/en-us/research/articles/the-art-of-building-verifiers-for-computer-use-agents/)\] as the baseline. Microsoft's verifier uses screenshots to audit browser-agent trajectories. Its LLM-as-a-verifier design first creates a task-specific rubric, checks which screenshots are relevant to each criterion, analyzes the selected evidence, and then produces criterion-level, process, and outcome scores.

We already had Microsoft's screenshot verifier implementation. We then built a DOM-based verifier with the same overall design and scoring behavior. The main difference is the evidence passed to it: **Microsoft's verifier receives screenshots, while our verifier receives ordered DOM files from the same browser trajectory.** 

**Setup of the experiment**

For the experiment, we used our own custom browser and ran the agent's tasks inside it. Each task execution produced the same trajectory in two evidence formats:  
\- a sequence of screenshots showing the browser viewport.  
\- a sequence of DOM files describing the browser state as text.

These are not two different agent attempts. Both evidence formats come from the same task execution and are paired with the same actions and final answer.

We created our own paired dataset for this experiment: [WootzappLab/browser-agent-tasks](https://huggingface.co/datasets/WootzappLab/browser-agent-tasks)

**Harness of the agent**

The agent performs a task inside our custom Wootz browser, coordinated by a Python harness that manages actions and records the run. At each step, the browser captures the page and converts its structured content into a readable file, `dom_model.txt`. (This same file is used for agent trajectory in DOM based Verifier). The model receives this text, references to interactive elements, and context from previous steps to decide what to do next. The harness checks the proposed action, `agent-browser` executes it, and the cycle repeats until the task ends.

**Verifier pipeline**

To make the comparison fair, we first generate **one frozen rubric** for each task. That exact same rubric \- with the same criteria, criterion order, maximum points, denominator, and hash is then passed to both verifiers. This ensures that the screenshot and DOM verifiers are being asked the same questions and scored against the same definition of success.

We then verified each recorded trajectory using both approaches: the Microsoft screenshot based verifier and our DOM based verifier.  
In both cases, the verifier evaluates the available browser states against the same frozen rubric. It identifies the states relevant to each criterion, analyzes the selected evidence, and then applies the same scoring, outcome, validity, retry, failure-classification, and reporting pipeline.

**Metric: Evidence loss**

The main metric we used to compare the two approaches is evidence loss: how often the evidence required for a rubric criterion is missing from one representation but available in the other.

\- **Screenshot evidence loss** means that the required evidence was not sufficiently captured in the screenshots but was present in the DOM.  
\- **DOM evidence loss** means that the required evidence was not sufficiently preserved in the DOM to verify the agent's trajectory.

We manually audited the missing evidence. This allowed us to separate a capture problem from a verifier reasoning problem. If evidence was present but the verifier interpreted it incorrectly, that was treated as a scoring or reasoning error, not evidence loss.

**Results**

Across 44 audited tasks containing 227 rubric criteria, the result was:

| Evidence Format | Evidence Loss |
| :---- | :---- |
| Screenshots | 6.2% (14/227 criteria) |
| DOM model | 2.6% (6/227criteria) |

The DOM therefore showed **3.6 % less evidence loss** than screenshots.  
Task based results are stored in:  
[https://github.com/wootzapp/wootzapp\_web\_browser-/blob/evidence-error-2/results.md](https://github.com/wootzapp/wootzapp_web_browser-/blob/evidence-error-2/results.md)

**What we observed**

The screenshot sequence did not always preserve the complete state of the agent's trajectory. An agent could correctly find information on a page, but that information might be outside the captured viewport, cut off, too difficult to read, or no longer visible in the next screenshot. The screenshot verifier could then penalize the trajectory because the evidence supplied to it did not prove what the agent had actually found.

This was particularly noticeable for **URL navigation**. The DOM records the URL explicitly, while a screenshot may shorten it, hide part of it, or make it difficult for the verifier to read.

The advantage of the DOM is that information such as text, labels, field values, buttons, selected controls, dialogs, errors, and final UI state can be stated explicitly. A screenshot may visually contain some of this information, but it can be difficult to read, clipped, hidden outside the viewport, or shown only in a shortened or relative form.
