# Proposed Paper Structure

## 1. Introduction

Establish the central problem: browser-agent evaluations depend on the evidence retained from an execution, but different representations can preserve different required facts.

Introduce the research question:

> For the same browser execution and verification rubric, what required evidence is available in screenshots versus DOM-derived records?

Briefly describe the paired recording and source-audit method.

State the headline finding:

- After excluding losses primarily attributed to URL identity while retaining the full denominator, screenshots have 34 detected evidence losses and DOM-derived records have 5, a difference of 4.52 percentage points.
- Frame this non-URL contrast as the main empirical result.
- Do not foreground the URL-loss count in the abstract. Introduce URL asymmetry later as an important sensitivity analysis and measurement-boundary issue.

Present `w8-domdiff-bench` as the code and paired source-audit protocol, and `browser-agent-tasks` as the companion dataset being open-sourced alongside it. Introduce the task definitions, paired trajectories, supporting recordings, frozen rubrics, verifier outputs, and source audits as a concrete release contribution.

State the scope clearly: the study measures recorded evidence availability, not verifier accuracy, agent success, or intrinsic superiority of one modality.

End with three concrete contributions:

- a paired source-audit protocol that separates evidence retention from verifier interpretation;
- a released dataset containing aligned screenshot and DOM-derived records with criterion-level audit findings;
- a reproducible empirical analysis centered on non-URL evidence loss and supported by URL and access-blocker sensitivity analyses.

## 2. Related Work

Organize the literature by the specific gap this paper addresses. Do not use this section as a list of browser-agent papers.

### 2.1 Browser Benchmarks and Observation Interfaces

Discuss WebArena, VisualWebArena, and BrowserGym as prior work on realistic browser tasks and multimodal or structured observation interfaces.

Explain the distinction from this paper: these systems evaluate task completion or provide observation interfaces, whereas this work audits which criterion-required facts survive in two aligned records of the same execution.

### 2.2 Trajectory Verification

Discuss WebVoyager, WebJudge, Universal Verifier, and human audits of WebArena-Lite.

Explain what Universal Verifier contributes: rubric-centered scoring, trajectory evidence selection, blocker handling, and process/outcome judgments.

Also state its relevant limitation for this study: a verifier can only reason over the evidence it receives. A wrong score may arise because evidence is missing or because available evidence is interpreted incorrectly. Universal Verifier does not by itself isolate these two causes, which motivates the separate source audit.

### 2.3 Observation Reduction and Evidence Retention

Discuss work on HTML or observation reduction, including Minimal Failure Set retention.

Distinguish the outcome here: this paper studies retrospective verification of a fixed trajectory against rubric criteria, rather than using retained elements as a proxy for acting-agent performance.

### 2.4 Positioning DOM-diff Optimized

Explain DOM-diff Optimized in enough detail for the reader to understand what is novel about the evaluated representation:

- it converts captured Chromium state into compact model-facing text;
- it organizes content, tables, controls, media descriptions, relationships, and scroll regions;
- despite its historical name, the evaluated output represents each state directly rather than requiring reconstruction from a separate diff;
- it is built on the `w8-core` Chromium recording stack.

State the unresolved comparison clearly: the study compares DOM-diff Optimized with screenshots, but does not isolate its improvements over a standard DOM dump, accessibility tree, or lightly filtered structured representation.

End Related Work with one concise positioning statement: prior work studies browser-agent execution, observation interfaces, and verification; this paper isolates criterion-level evidence retention across paired records of the same execution.

## 3. Problem Definition

Define the concepts before introducing implementation details:

- task;
- trajectory;
- rubric;
- criterion;
- required evidence;
- screenshot representation;
- DOM representation;
- evidence availability;
- directional evidence loss;
- source loss versus verifier error.

Use only the notation needed to understand the analysis. Explain every symbol in plain language before when it appears.

## 4. Study Design

### 4.1 Paired Comparison

Explain that the comparison holds the task, executed actions, final answer, rubric, and trajectory fixed. Only the retained evidence representation varies.

Clarify that this measures the two representations of a particular trajectory. It does not compare screenshot-conditioned and DOM-conditioned acting agents.

### 4.2 Recording Channels

Describe what each channel contains and what it cannot contain.

For screenshots, explain the viewport and browser-chrome limitations. For DOM-derived records, explain page identity, filtering, grouping, and off-screen coverage limitations.

Emphasize that observed differences are gaps in recorded evidence, not necessarily intrinsic limitations of screenshots or DOM representations.

### 4.3 Source Audit

Define the source audit in simple terms: an audit of whether each criterion-required item is present in the eligible retained states for each representation.

Describe the audit inputs, including ordered source states, shared trajectory context, rubric information, and verifier outputs.

Explain how a source citation and loss flag make each finding inspectable.

### 4.4 Loss Categories and Sensitivity Analyses

Define the primary categories:

- exact text and values;
- URLs and page identity;
- control states;
- table entries;
- label–value relationships;
- capture omissions.

Explain that each representation–criterion loss receives one primary category, even when multiple omissions may exist.

Define the two URL sensitivities:

1. primary-category filtering, which removes URL-attributed losses from the numerator but retains every criterion;
2. whole-criterion exclusion, which removes every criterion with a primary URL loss.

Explain why these answer different questions.

### 4.5 Counts and Rates

Define the screenshot loss rate, DOM loss rate, and paired screenshot-minus-DOM difference.

Explain that the rates describe the saved corpus and count affected criteria. One missing item can affect several criteria, so the counts do not represent independent capture failures. Keep the original bootstrap calculation in the reproducibility appendix for compatibility with archived results.

## 5. Dataset and Experimental Setup

### 5.1 Task Corpus

Describe the 100 public-web research and extraction tasks, their criteria, hostnames, task types, and action histories.

State what the corpus does and does not cover, especially with respect to long-horizon, transactional, authenticated, and visually intensive workflows.

### 5.2 Dataset Contents and Reuse

Describe the companion `browser-agent-tasks` release using its actual layout: `tasks.jsonl`, `trajectories/data-ss/`, `trajectories/data-dom/`, `recordings/`, and `evaluation/`.

Explain the shared task metadata, final answers, action logs, numbered screenshot and DOM observations, and supporting collection artifacts. Describe how readers can inspect audit findings, evaluate verifiers against frozen rubrics, or analyze evidence selection.

Clarify that the task catalog's `train` split is a loader configuration rather than a validated training partition.

### 5.3 Trajectory Generation

Describe the acting model and its DOM-conditioned inputs.

Explain why this matters: the paired comparison controls the trajectory but does not estimate how a screenshot-conditioned policy would behave.

### 5.4 Verifier Setup

Explain that both verifiers use the same models, rubric, and scoring controls, with the evidence loader varying.

State explicitly that verifier-score differences are not the primary outcome; the analysis concerns source-audit labels.

### 5.5 Provenance and Quality Controls

Briefly describe preflight validation, action alignment, state ordering, rubric hashes, pinned dataset revisions, and audit-file checks.

Move detailed software-stack information, commands, and file paths to an appendix.

## 6. Results

### 6.1 Main Non-URL Evidence-Loss Result

Present the non-URL primary-category result first as the main result: 34 screenshot losses, 5 DOM losses, and a 4.52 percentage-point difference over all 642 criteria.

State the result in plain language immediately after the table: how often each representation loses criterion-required evidence and how large the paired difference is.

Explain overlapping losses and why a criterion can have losses in both representations.

### 6.2 Full-Corpus Result and URL Sensitivity

Report the all-category counts here, after the main non-URL result, rather than using them as the paper’s opening empirical claim.

Show that URL identity accounts for most of the screenshot-side findings.

Explain the metadata asymmetry clearly: screenshots omit the browser address bar while the DOM-derived record contains page-identity metadata.

Avoid presenting the URL finding as a property of screenshots in general; frame it as a property of this capture configuration and audit rule.

### 6.3 Types of Losses

Use a compact category table and a small number of concrete examples:

- an exact timestamp or value;
- off-screen or viewport coverage;
- mathematical notation;
- a control state;
- a label–value relationship.

Label these as illustrative examples and connect each to the relevant category.

### 6.4 Robustness Checks

Report the access-blocked-task analysis and alternative URL exclusions using counts, rates, and differences.

Keep interpretation concise; reserve broader implications for the Discussion.

## 7. Discussion

### 7.1 Evidence Availability Is a Separate Evaluation Variable

Explain why verifier accuracy and source-evidence availability answer different questions.

Discuss how a missing item may or may not change a verifier’s final judgment.

### 7.2 Metadata Parity as a Baseline

Define metadata parity as giving both representations equivalent identity and tab metadata.

Explain why screenshot-plus-URL metadata is an important future comparator.

### 7.3 Implications for Benchmark and Verifier Design

Discuss reporting evidence availability alongside verifier outcomes and inspecting representation-specific losses before interpreting score differences.

### 7.4 Future Comparisons

Motivate controlled comparisons with:

- ordinary DOM;
- accessibility trees;
- lightly filtered structured records;
- screenshot-plus-metadata inputs;
- combined screenshot and DOM evidence.

## 8. Limitations

Keep the limitations together and state them directly:

- the corpus contains 100 selected public-web tasks;
- there is one trajectory per task;
- the acting policy is DOM-conditioned;
- audit labels are model-generated and internally reviewed;
- screenshot and DOM capture are sequential;
- evidence missing from both channels cannot be detected by the paired comparison;
- the renderer is not isolated through a controlled ablation;
- the study does not measure verifier accuracy or agent performance;
- descriptive rates do not establish population representativeness;
- annotation mistakes can affect the counts.

## 9. Conclusion

Use three short paragraphs:

1. Restate the problem: evaluations depend on what their records preserve.
2. State the main finding: a non-URL evidence-loss difference remains after URL-attributed findings are removed from the numerator; then note that URL metadata explains most of the larger all-category contrast.
3. State the precise contribution: a paired source-audit framework for separating missing recorded evidence from verifier interpretation and task outcome.

Avoid introducing new caveats or technical details here.

## 10. References

Include a conventional reference list before the appendices. Every work discussed in Related Work should appear here, and every listed work should be cited in the paper.

The initial reference set should include:

- Enomoto et al. (2026), *Revisiting Observation Reduction for Web Agents: Comprehensive Evaluation with a Lightweight Framework*.
- Gan et al. (2026), *Auditing Web Agent Evaluation on WebArena-Lite: Human Review of Outcomes and Trajectories*.
- He et al. (2024), *WebVoyager: Building an End-to-End Web Agent with Large Multimodal Models*.
- Koh et al. (2024), *VisualWebArena: Evaluating Multimodal Agents on Realistic Visual Web Tasks*.
- Le Sellier de Chezelles et al. (2025), *The BrowserGym Ecosystem for Web Agent Research*.
- Rosset et al. (2026), *The Art of Building Verifiers for Computer Use Agents*.
- Xue et al. (2025), *An Illusion of Progress? Assessing the Current State of Web Agents*.
- Zhou et al. (2024), *WebArena: A Realistic Web Environment for Building Autonomous Agents*.
- The pinned `w8-domdiff-bench` dataset release and technical report.

Use one citation style consistently. Keep project artifacts separate from scholarly references if the target venue prefers a dedicated Data and Code Availability section.

## Appendices

### Appendix A. Formal Definitions and Equations

Place the full notation, loss indicators, rate definitions, and paired difference here.

### Appendix B. Recording and Verifier Implementation Details

Describe the browser stack, `w8-core`, ChromiumRL, DevTools Protocol, `agent-browser`, state construction, preflight checks, and verifier controls.

### Appendix C. Dataset Provenance and Audit-Label Reconstruction

Document pinned revisions, hashes, source files, category assignments, extraction checks, and reconciliation procedures.

### Appendix D. Full Statistical Reanalysis

Provide the complete reanalysis procedure, sensitivity definitions, and interpretation boundaries. Retain the original bootstrap settings only as documentation of the archived computation, outside the main paper's narrative and findings.

### Appendix E. Complete Tables and Reproducibility Materials

Include complete per-task and per-criterion tables, embedded programs, reference results, source manifests, and instructions for reproducing the saved-label statistics.

## Editorial Principle

The paper should introduce the research question and headline result before implementation details, equations, hashes, and reproducibility machinery. Every technical detail should support the central story:

> For a fixed browser execution and rubric, different retained representations preserve different amounts and kinds of criterion-required evidence.



