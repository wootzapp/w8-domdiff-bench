# Recreating the Universal Verifier: End-to-End Design, Iterations, Theory, and Math

> Based on **“The Art of Building Verifiers for Computer Use Agents”** (Rosset et al., 2026).
>
> **Important distinction:** the paper explicitly specifies the **final runtime pipeline** in Algorithm 1. It does **not** publish the exact commit-by-commit order in which the human expert discovered every component.  
> The “V0 → V1 → …” sequence below is therefore a **pedagogical reconstruction**: it shows how the final architecture can naturally emerge from repeated verifier failures. The runtime architecture, formulas, call counts, process/outcome separation, relevance matrix, evidence taxonomy, and evaluation procedure are directly grounded in the paper.

---

# 1. What is a verifier in this paper?

A verifier is not a separately trained “verifier model.”

It is a Python program that:

1. receives the user task and the agent trajectory,
2. calls one or more LLMs or multimodal LLMs,
3. passes structured intermediate outputs between those calls,
4. performs deterministic operations such as top-k selection and score normalization,
5. returns a process score, an outcome label, and a failure report.

The complete system is:

```text
Universal Verifier = pipeline code + prompts + multimodal LLM judgments
```

The **model** performs semantic judgments such as:

- understanding the task,
- generating rubric criteria,
- reading screenshots,
- assigning criterion points,
- detecting hallucinations,
- deciding final task success.

The **code** performs orchestration such as:

- loading screenshots and action history,
- calling the model,
- parsing JSON,
- building matrices,
- selecting top-k,
- computing normalized scores,
- taking medians and majority votes,
- saving the final report.

---

# 2. Formal problem definition

A computer-use task is represented as:

```text
(g,E)
```

where:

- `g` is the user’s natural-language goal,
- `E` is the computer or browser environment.

The agent interacts with `E` and generates a trajectory:

```text
τ=(s_0,a_1,s_1,a_2,…,a_T,s_T)
```

where:

- `s_t` is the screenshot or visual state at time `t`,
- `a_t` is an action such as click, type, scroll, or navigate,
- `T` is the number of interaction steps.

The verifier is:

```text
V(g,τ) = (r_proc,r_out,d)
```

where:

- `r_proc∈[0,1]`: process score,
- `r_out∈{0,1}`: binary outcome success,
- `d`: structured failure diagnosis.

The central design idea is that **process and outcome are different questions**:

- **Process:** Did the agent act reasonably and correctly given the environment?
- **Outcome:** Did the user actually receive the requested result?

---

# 3. How a verbal verifier rule becomes code

Suppose the first verifier is only:

```python
def verify(task, actions, final_answer) -> bool:
    prompt = f"""
    Task:
    {task}

    Agent actions:
    {actions}

    Agent final answer:
    {final_answer}

    Did the agent complete the task?
    Return true or false.
    """

    response = call_llm(prompt)
    return response == "true"
```

This is already a verifier:

```text
V_0(g,τ)→{0,1}
```

It is simply a weak verifier.

If developers discover:

> “It trusts the agent’s claimed final answer.”

they can modify the system at different levels.

## Prompt-only change

```python
prompt += """
Do not trust the final answer.
Check whether the screenshots support it.
"""
```

This is easy, but weak.

## Input change

```python
def verify(task, actions, final_answer, screenshots):
```

Now screenshots are attached to the multimodal model request.

## Structural change

Instead of one overloaded call:

```python
return one_model_call(...)
```

split the verifier into independent stages:

```python
action_report = score_without_screenshots(...)
visual_report = inspect_screenshots(...)
result = reconcile(action_report, visual_report)
return result
```

This is the key engineering pattern in the paper:

```text
Do not only add instructions; decompose the judgment into separate model calls.
```

---

# 4. Pedagogical development: from a naive verifier to the final architecture

The following versions explain how the final Universal Verifier can be understood as a sequence of responses to specific failures.

---

## Version 0 — One text-only outcome judge

### Code idea

```python
def verify_v0(task, actions, final_answer):
    return llm_binary_judge(
        task=task,
        actions=actions,
        final_answer=final_answer,
    )
```

### Mathematical form

```text
ŷ = f_θ(g,a_1:T,final answer)
```

where:

```text
ŷ∈{0,1}
```

### Failure

The verifier may trust:

> “I successfully completed the purchase.”

even if the agent never reached checkout.

### Theory

The final answer is **agent-generated evidence**, not ground truth.

A verifier should distinguish:

```text
agent claim ≠ environment state
```

This motivates adding screenshots.

---

## Version 1 — Give screenshots to the multimodal judge

### Code change

```python
def verify_v1(task, actions, final_answer, screenshots):
    return multimodal_binary_judge(
        task=task,
        actions=actions,
        final_answer=final_answer,
        screenshots=screenshots,
    )
```

### New input

```text
V_1(g,τ) = f_θ(g,a_1:T,s_0:T,final answer)
```

### Why this helps

The model can now compare the claimed success with visible browser state.

### New failure

For long trajectories:

- there may be dozens or hundreds of screenshots,
- important evidence may appear only briefly,
- one giant context becomes a visual needle-in-a-haystack problem.

There is another subtle issue:

> If the scorer sees the correct information in a screenshot, it may accidentally “fill in” something the agent never actually said or established.

This motivates two separate ideas:

1. create a task-specific rubric,
2. score once without screenshots and later rescore with screenshots.

---

## Version 2 — Generate a rubric before seeing the trajectory

Instead of asking one vague question:

> “Did the agent succeed?”

the verifier first converts the user task into `N` concrete criteria:

```text
C={c_1,c_2,…,c_N}
```

Each criterion `c_j` contains:

- a description,
- maximum points `w_j`,
- scoring guidance,
- possibly a condition.

### Code structure

```python
rubric = generate_rubric(task)
```

The rubric generator sees only:

```text
g
```

It does not see the trajectory.

### Why generation and scoring are separated

If the same LLM sees the trajectory while generating the rubric, it can tailor the criteria to the agent’s behavior.

Formally, we want:

```text
C∼ p(C| g)
```

not:

```text
C∼ p(C| g,τ)
```

because the second form allows confirmation bias.

### Criterion theory

#### Phantom criteria

A criterion must be necessary for satisfying `g`.

A phantom criterion adds an unrequested requirement, inflating the denominator:

```text
r_proc = (earned points) / (possible points)
```

If irrelevant criteria increase the denominator, an otherwise correct agent is unfairly penalized.

#### Non-overlapping criteria

Each criterion should evaluate a distinct semantic requirement.

For two criteria `c_i,c_j`, ideal overlap is small:

```text
Overlap(c_i,c_j)≈ 0
```

This is conceptual rather than a numeric function in the paper.

#### Cascading-error-free criteria

Suppose criterion `c_2` depends on the output of `c_1`.

A single mistake in `c_1` should not automatically create a second penalty if the agent’s later behavior was reasonable under its current belief.

The intended scoring principle is:

```text
score(c_j) = quality of behavior at c_j given the information available then
```

not:

```text
score(c_j) = 0 whenever an upstream criterion failed
```

### Dependency-checking stage

The final system includes a separate LLM call that audits the initial rubric:

```python
initial_rubric = generate_rubric(task)
rubric = check_dependencies(task, initial_rubric)
```

It checks for:

- duplicated requirements,
- dependencies,
- cascading penalties,
- conditional conflicts,
- invented requirements.

---

## Version 3 — Action-history-only scoring

The verifier now scores each criterion using:

- task,
- rubric,
- action history,
- final answer,

but **not screenshots**.

For criterion `c_j`:

```text
p_j^action∈[0,w_j]
```

### Code

```python
action_scores = score_action_history(
    task=task,
    rubric=rubric,
    actions=actions,
    final_answer=final_answer,
)
```

### Why this stage exists

It builds a ledger of:

- what the agent attempted,
- what it claimed,
- what its textual actions support,
- what remains unsupported.

This prevents the visual scorer from using screenshot information to silently repair the agent’s incorrect or missing claims.

### Conceptual comparison

Later, the verifier will compare:

```text
p_j^action with p_j^visual
```

A large discrepancy can indicate:

- contradiction,
- fabrication,
- omission,
- unsupported final claims.

---

## Version 4 — Build the screenshot–criterion relevance matrix

The rubric now defines the questions. The verifier must find visual evidence for each question.

Let:

- `M=T+1`: number of screenshots,
- `N`: number of criteria.

The verifier builds:

```text
R ∈ ℝ^(M×N)
```

where:

```text
R_ij = Rel(s_i,c_j)
```

is the relevance of screenshot `s_i` to criterion `c_j`.

### Example

| Screenshot | Product identity | Correct listing | Checkout state |
|---|---:|---:|---:|
| `s_0` | 1 | 0 | 0 |
| `s_5` | 8 | 1 | 0 |
| `s_9` | 10 | 0 | 0 |
| `s_28` | 0 | 9 | 2 |
| `s_45` | 0 | 3 | 10 |

### Model versus code

The **multimodal model** returns relevance scores.

```python
row_i = relevance_model(
    screenshot=s_i,
    criteria=rubric,
)
```

The **Python code** stores the rows:

```python
R = np.asarray(relevance_rows)
```

### Call complexity

Each screenshot is scored against all criteria in one call.

So the number of calls is:

```text
M
```

not:

```text
M× N
```

although each call semantically considers all `N` criteria.

These `M` calls are issued in parallel.

---

## Version 5 — Select top-K evidence separately for every criterion

For criterion `c_j`, select:

```text
S_j = TopK_i R_ij
```

where:

```text
S_j⊆{s_0,…,s_T}, |S_j|≤ K
```

### Code

```python
selected[j] = top_k_indices(R[:, j], k=K)
```

### Why this matters

The verifier does not select one global screenshot set.

It creates:

```text
Criterion 1 → screenshots 5, 7, 9
Criterion 2 → screenshots 28, 31, 34
Criterion 3 → screenshots 43, 45, 46
```

The rubric therefore becomes the organizing axis of visual retrieval.

### Tie-breaking

When scores tie, later screenshots are preferred because they usually contain the more current state.

### Pruning

The paper describes a heuristic:

- if a criterion already has a highly relevant screenshot with score above 7,
- earlier screenshots with score below 5 may be discarded.

These are implementation optimizations, not the core mathematical idea.

---

## Version 6 — Extract criterion-specific visual evidence

For every selected pair:

```text
(c_j,s_i), s_i∈ S_j
```

the verifier extracts:

```text
e_ij = E_θ(c_j,s_i)
```

where `e_ij` is structured evidence.

### Code

```python
evidence = extract_evidence(
    criterion=c_j,
    screenshot=s_i,
)
```

### Example output

```json
{
  "criterion_id": "c1",
  "screenshot_id": 9,
  "visible_evidence":
    "The page says 'Cardon Purifying Clay Cleanser'.",
  "supports_criterion": true
}
```

### Why evidence extraction is separate from scoring

The model first answers:

> “What is visibly present?”

Only later does another stage answer:

> “How many points should this earn?”

This reduces premature judgment.

### Batching

Let:

```text
S = |⋃_(j=1 to N) S_j|
```

be the number of unique selected screenshots.

A screenshot that supports several criteria can be analyzed once against all relevant criteria.

The evidence-analysis call count satisfies:

```text
S≤ K N
```

and these calls can also run in parallel.

---

## Version 7 — Resolve conditional criteria using evidence

Some criteria depend on the environment.

Example:

> “Report the window-seat cost if an eligible direct flight exists.”

Define:

```text
z_j = 1 if c_j applies; 0 if c_j does not apply
```

The active set is:

```text
A={j:z_j=1}
```

### Code

```python
active_rubric = resolve_conditions(
    rubric=rubric,
    evidence=evidence,
)
```

### Theory

If no eligible flight exists, the seat-cost criterion is impossible.

It should therefore be excluded from both numerator and denominator.

This is different from giving zero points.

Zero means:

> The criterion applied, but the agent failed it.

Exclusion means:

> The criterion did not apply in reality.

---

## Version 8 — Reality check

The verifier now reconciles:

- initial rubric assumptions,
- action-only report,
- screenshot evidence,
- environmental blockers.

### Code

```python
reality_notes = reality_check(
    task=task,
    rubric=active_rubric,
    action_scores=action_scores,
    evidence=evidence,
)
```

### Example reality notes

```text
The requested product existed.
No CAPTCHA blocked the agent.
The final screenshot shows the cart, not completed checkout.
The agent had no permission to cross the payment boundary.
```

### Controllability theory

The verifier distinguishes:

```text
controllable failure vs. uncontrollable failure
```

#### Uncontrollable

- CAPTCHA,
- login wall without credentials,
- site outage,
- item out of stock,
- no matching result.

#### Controllable

- wrong product,
- wrong date,
- reasoning error,
- unsupported claim,
- premature stop,
- skipped filter.

This distinction mainly affects process scoring.

An agent can execute correctly but still fail the real-world outcome:

```text
r_proc≈1, r_out=0
```

---

## Version 9 — Multimodal rescoring

The final criterion score is produced after combining:

- task,
- criterion,
- action-only score,
- relevant visual evidence,
- reality notes.

For criterion `j`:

```text
p_j = f_θ ( g, c_j, p_j^action, {e_ij:s_i∈ S_j}, reality notes )
```

with:

```text
p_j∈[0,w_j]
```

### Code

```python
final_scores = rescore_with_evidence(
    task=task,
    rubric=active_rubric,
    action_scores=action_scores,
    evidence=evidence,
    reality_notes=reality_notes,
)
```

### Visual evidence taxonomy

The paper uses five important cases.

#### 1. Contradiction

Screenshots show `X`, agent claims `¬ X`.

```text
visual state ≠ agent claim ⇒failure
```

#### 2. Fabrication

Agent claims `X`, but no evidence supports `X`.

```text
P(evidence for X|τ)≈0 ⇒failure
```

#### 3. Omission

The agent did not inspect all necessary alternatives.

Example: checking only one division when the task asks for the highest-ranked team in the whole conference.

#### 4. Supported inference from absence

If the screenshots thoroughly show that no booking UI exists, the agent may reasonably conclude that online booking is unavailable.

#### 5. Visual confirmation without explicit text

The agent may omit a verbal justification, while screenshots still visibly confirm the correct result.

Only contradiction, fabrication, and omission are penalized in this taxonomy.

---

## Version 10 — Detect unsolicited side effects

The original rubric describes expected behavior, but cannot predict every harmful extra action.

So a separate model call searches the trajectory for:

- extra cart items,
- unwanted subscriptions,
- warranties,
- unauthorized substitutions,
- persistent modifications,
- crossing a transactional boundary without permission.

### Code

```python
side_effects = detect_side_effects(
    task=task,
    trajectory=trajectory,
    existing_rubric=active_rubric,
)
```

### Penalty formulation

Conceptually, the verifier augments the rubric:

```text
C^+ = C∪ C_side-effect
```

For a penalty criterion `q`:

```text
p_q=0, w_q>0
```

This lowers the normalized process score.

A serious side effect also typically causes:

```text
r_out=0
```

---

## Version 11 — Compute the process score

Let:

- `w_j`: maximum points,
- `p_j`: earned points,
- `z_j`: applicability indicator.

Then:

```text
r_proc = (Σ_j=1^Nz_jp_j) / (Σ_j=1^Nz_jw_j)
```

Equivalently:

```text
r_proc = (Σ_j∈ Ap_j) / (Σ_j∈ Aw_j)
```

### Example

| Criterion | Earned | Maximum |
|---|---:|---:|
| Search correct route | 2 | 2 |
| Determine availability | 7 | 7 |
| Report seat cost | 1 | 4 |

```text
r_proc = (2+7+1) / (2+7+4) = (10) / (13) ≈0.769
```

For benchmark evaluation, the paper binarizes process success at:

```text
ŷ_proc = mathbf1[r_proc≥0.8]
```

Here:

```text
ŷ_proc=0
```

The native process score itself remains continuous.

---

## Version 12 — Run a separate outcome verifier

The process score is not automatically converted into outcome success.

A separate model call asks:

> “Would a reasonable user consider the requested goal complete?”

### Code

```python
outcome = verify_outcome(
    task=task,
    process_score=process_score,
    rubric_scores=final_scores,
    evidence=evidence,
    reality_notes=reality_notes,
    side_effects=side_effects,
    final_answer=final_answer,
)
```

### Mathematical output

```text
r_out∈{0,1}
```

### Why this must be separate

#### Environment blocker

```text
Agent behaved correctly.
CAPTCHA prevented completion.
```

Then:

```text
r_proc≈1, r_out=0
```

#### Unexpected but valid route

```text
Agent used a different source,
but delivered the correct result.
```

Then:

```text
r_proc≈1, r_out=1
```

#### Correct-looking process, wrong final answer

Then both can fail:

```text
r_proc<1, r_out=0
```

---

## Version 13 — Reduce stochastic variance through voting

LLM judgments are nondeterministic.

Run important scoring stages `Q=N_vote` times.

### Process aggregation

```text
r_proc = median ( r_proc^(1), …, r_proc^(Q) )
```

### Outcome aggregation

```text
r_out = mathbf1 [ Σ_q=1^Qr_out^(q) > (Q) / (2) ]
```

So:

- continuous scores use the median,
- binary labels use majority vote.

---

## Version 14 — Diagnose and localize failures

The final output includes a structured diagnostic report:

```text
d= {(t_ℓ,z_ℓ,h_ℓ)}_ℓ=1^L
```

where:

- `t_ℓ`: failure step,
- `z_ℓ`: taxonomy code,
- `h_ℓ`: explanation and evidence.

### Example

```json
{
  "step": 41,
  "category": "Output contradiction",
  "description":
    "The agent reported USD 89, while screenshot 41 shows USD 109."
}
```

The paper’s taxonomy includes seven broad groups:

1. selection,
2. hallucination,
3. execution and strategy,
4. critical point,
5. task ambiguity,
6. side effect,
7. tool interaction.

---

# 5. The final runtime pipeline

For one new trajectory:

```text
Task + actions + screenshots + final answer
                    ↓
1. Generate initial rubric from task only
                    ↓
2. Check rubric dependencies and conflicts
                    ↓
3. Score action history without screenshots
                    ↓
4. Score every screenshot against every criterion
                    ↓
5. Build relevance matrix R
                    ↓
6. Select top-K screenshots per criterion
                    ↓
7. Extract visual evidence e_ij
                    ↓
8. Resolve conditional criteria z_j
                    ↓
9. Run reality check
                    ↓
10. Rescore criteria with visual evidence
                    ↓
11. Detect unsolicited side effects
                    ↓
12. Compute process score r_proc
                    ↓
13. Independently judge outcome r_out
                    ↓
14. Diagnose and localize failures d
```

---

# 6. Simplified end-to-end Python structure

```python
async def universal_verify(
    task,
    actions,
    screenshots,
    final_answer,
    *,
    top_k=5,
    num_votes=3,
):
    # Phase 1: Build task-specific verification specification
    initial_rubric = await generate_rubric(task)

    rubric = await check_dependencies(
        task=task,
        rubric=initial_rubric,
    )

    action_scores = await score_action_history(
        task=task,
        rubric=rubric,
        actions=actions,
        final_answer=final_answer,
    )

    # Phase 2: Retrieve visual evidence
    relevance_rows = await asyncio.gather(*[
        score_screenshot_relevance(
            task=task,
            rubric=rubric,
            screenshot=screenshot,
        )
        for screenshot in screenshots
    ])

    R = np.asarray(relevance_rows)

    selected = select_top_k_per_criterion(
        relevance_matrix=R,
        k=top_k,
    )

    screenshot_batches = group_by_screenshot(selected)

    evidence_batches = await asyncio.gather(*[
        extract_evidence(
            task=task,
            screenshot=screenshots[screenshot_id],
            criteria=criteria,
        )
        for screenshot_id, criteria
        in screenshot_batches.items()
    ])

    evidence = unpack_evidence(evidence_batches)

    active_rubric = await resolve_conditions(
        task=task,
        rubric=rubric,
        evidence=evidence,
    )

    reality_notes = await reality_check(
        task=task,
        rubric=active_rubric,
        actions=actions,
        final_answer=final_answer,
        action_scores=action_scores,
        evidence=evidence,
    )

    # Phase 3: Score and aggregate
    process_runs = await asyncio.gather(*[
        rescore_with_evidence(
            task=task,
            rubric=active_rubric,
            actions=actions,
            final_answer=final_answer,
            action_scores=action_scores,
            evidence=evidence,
            reality_notes=reality_notes,
        )
        for _ in range(num_votes)
    ])

    side_effect_runs = await asyncio.gather(*[
        detect_side_effects(
            task=task,
            actions=actions,
            screenshots=screenshots,
            final_answer=final_answer,
        )
        for _ in range(num_votes)
    ])

    scored_runs = [
        apply_side_effect_penalties(process, side_effects)
        for process, side_effects
        in zip(process_runs, side_effect_runs)
    ]

    process_score = median([
        run.normalized_score
        for run in scored_runs
    ])

    outcome_runs = await asyncio.gather(*[
        verify_outcome(
            task=task,
            process_score=process_score,
            rubric_scores=scored_runs,
            final_answer=final_answer,
            evidence=evidence,
            reality_notes=reality_notes,
            side_effects=side_effect_runs,
        )
        for _ in range(num_votes)
    ])

    outcome = majority_vote([
        run.success
        for run in outcome_runs
    ])

    diagnosis = await diagnose_failures(
        task=task,
        actions=actions,
        screenshots=screenshots,
        rubric_scores=scored_runs,
        evidence=evidence,
        outcome=outcome,
    )

    return {
        "process_score": process_score,
        "outcome": outcome,
        "diagnosis": diagnosis,
    }
```

---

# 7. Model responsibilities versus code responsibilities

| Stage | Model | Code |
|---|---|---|
| Rubric generation | Understands task, writes criteria | Calls model, parses JSON |
| Dependency check | Detects overlaps and dependencies | Passes rubric to next stage |
| Action-only score | Assigns criterion points | Stores results |
| Relevance scoring | Scores screenshot relevance | Builds matrix `R` |
| Top-K | — | Sorts and selects indexes |
| Evidence extraction | Reads screenshots | Batches calls |
| Conditional resolution | Decides whether condition holds | Removes inactive criteria |
| Reality check | Interprets environment | Stores reality notes |
| Final rescoring | Assigns evidence-grounded points | Normalizes totals |
| Side effects | Detects unrequested actions | Applies penalties |
| Outcome | Judges user-level completion | Majority vote |
| Diagnosis | Classifies failure | Saves structured report |

---

# 8. LLM call-count math

Let:

- `M`: number of screenshots,
- `N`: number of rubric criteria,
- `K`: maximum selected screenshots per criterion,
- `S`: number of unique screenshots selected,
- `Q=N_vote`.

The paper’s call structure is approximately:

| Stage | Calls |
|---|---:|
| Initial rubric generation | `1` |
| Dependency checking | `1` |
| Action-only scoring | `1` |
| Screenshot relevance | `M` |
| Top-K grouping | `0` |
| Evidence analysis | `S≤ KN` |
| Condition resolution | `≤1` |
| Reality check | `1` |
| Multimodal rescoring | `Q` |
| Side-effect detection | `Q` |
| Outcome verification | `Q` |

Ignoring a separately counted diagnostic call:

```text
C_calls ≈ 3+M+S+1+1+3Q
```

Therefore:

```text
C_calls ≈ M+S+5+3Q
```

When `Q=1`:

```text
C_calls = M+S+8
```

The paper gives a typical example:

```text
M=47, N=3, K=5, S=10
```

Therefore:

```text
47+10+8=65
```

LLM calls, with the relevance and evidence stages heavily parallelized.

---

# 9. How the verifier itself was improved using labeled trajectories

The human-labeled trajectories are not shown to the verifier as answers.

They are used only to evaluate candidate versions.

For trajectory `m`:

```text
ŷ_m = V_θ(g_m,τ_m)
```

is the verifier prediction.

The human label is:

```text
y_m
```

The evaluation code compares:

```text
ŷ_m against y_m
```

The candidate verifier evolves:

```text
V_0 → V_1 → V_2 → ·s → V_final
```

Each version changes:

- prompts,
- model inputs,
- stage decomposition,
- thresholds,
- score calibration,
- aggregation,
- code structure.

---

## Confusion matrix

| | Human success | Human failure |
|---|---:|---:|
| Verifier success | TP | FP |
| Verifier failure | FN | TN |

### False-positive rate

```text
FPR = (FP) / (FP+TN)
```

This measures how often the verifier incorrectly rewards a failed trajectory.

For RL, false positives are especially dangerous because the agent can learn to exploit them.

### False-negative rate

```text
FNR = (FN) / (FN+TP)
```

This measures how often a correct trajectory is incorrectly rejected.

### Precision

```text
Precision = (TP) / (TP+FP)
```

### Recall

```text
Recall = (TP) / (TP+FN)
```

### F1

```text
F_1 = (2·Precision·Recall) / (Precision+Recall)
```

---

## Cohen’s `κ`

The paper uses Cohen’s `κ` to measure agreement beyond chance:

```text
κ = (p_o-p_e) / (1-p_e)
```

where:

- `p_o`: observed agreement,
- `p_e`: agreement expected from marginal label frequencies.

Interpretation:

- `κ=1`: perfect agreement,
- `κ=0`: chance-level agreement,
- `κ<0`: worse than chance.

The development objective can be expressed as:

```text
max_θ κ(θ)
```

subject to:

```text
FPR(θ_new) ≤ FPR(θ_old)
```

The paper’s auto-research setup explicitly rolled back changes that increased FPR.

---

## Iterative development loop

```text
Current candidate verifier V_i
              ↓
Run on labeled trajectories
              ↓
Compare predictions with human labels
              ↓
Calculate κ, FPR, FNR, F1
              ↓
Inspect false positives and false negatives
              ↓
Find a general design failure
              ↓
Modify prompts, inputs, code, or stage structure
              ↓
Create V_(i+1)
              ↓
Rerun evaluation
              ↓
Commit improvement or roll it back
```

This is not circular.

They do not use the finished verifier to build itself.

They repeatedly run the **current imperfect candidate verifier** and improve it.

---

# 10. Suggested project structure for recreating it

```text
universal_verifier/
│
├── schemas/
│   ├── rubric.py
│   ├── evidence.py
│   ├── scores.py
│   └── diagnosis.py
│
├── prompts/
│   ├── rubric_generation.md
│   ├── dependency_check.md
│   ├── action_only_score.md
│   ├── relevance_score.md
│   ├── evidence_extraction.md
│   ├── condition_resolution.md
│   ├── reality_check.md
│   ├── multimodal_rescore.md
│   ├── side_effect_detection.md
│   ├── outcome_verification.md
│   └── failure_diagnosis.md
│
├── stages/
│   ├── rubric.py
│   ├── action_score.py
│   ├── relevance.py
│   ├── evidence.py
│   ├── conditions.py
│   ├── reality.py
│   ├── rescore.py
│   ├── side_effects.py
│   ├── outcome.py
│   └── diagnosis.py
│
├── orchestration/
│   ├── pipeline.py
│   ├── voting.py
│   └── batching.py
│
├── evaluation/
│   ├── metrics.py
│   ├── compare_humans.py
│   └── error_analysis.py
│
└── main.py
```

---

# 11. Exact reproduction versus architectural recreation

The paper supports recreation of the architecture, but exact behavior additionally requires the authors’ released implementation.

The PDF does not print every detail of:

- roughly 2,000 lines of prompts,
- exact JSON schemas,
- all calibration examples,
- decoding settings,
- every point-weighting rule,
- side-effect severity rules,
- exact voting configuration for every experiment.

Therefore:

## Architectural recreation

Implement the pipeline described above.

## Exact reproduction

Use the official code, prompts, model versions, schemas, and configurations.

---

# 12. Simple mental model

A naive verifier is:

```text
Task + trajectory
        ↓
One LLM call
        ↓
PASS / FAIL
```

The Universal Verifier is:

```text
Task
  ↓
Generate a task-specific checklist
  ↓
Ask what the agent itself actually did and claimed
  ↓
Find the best visual evidence for every checklist item
  ↓
Read that evidence
  ↓
Resolve which checklist items actually apply
  ↓
Correct agent claims using visual reality
  ↓
Assign criterion points
  ↓
Check for harmful extra actions
  ↓
Compute process score
  ↓
Separately ask whether the user’s goal was achieved
  ↓
Explain where and why the agent failed
```

The shortest useful formula is:

```text
LLM creates specification → C; LLMs locate evidence → R,S_j; LLMs interpret evidence → e_ij; LLM assigns points → p_j; Code normalizes points → r_proc; LLM judges completion → r_out; LLM diagnoses failure → d
```

And the simplest engineering sentence is:

> **The model makes judgments; the code decides which judgment happens when, what evidence it receives, and how all judgments are combined.**