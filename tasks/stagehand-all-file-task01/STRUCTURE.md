# stagehand-all-file-task01 structure

This task uses the compact Stagehand flow layout. Each `step_XXX/` keeps the normal agent trajectory files plus a small `stagehand_flow/` folder showing how Stagehand converted page context into an internal action.

```text
tasks/stagehand-all-file-task01/
├── task.json
├── trajectory.jsonl
├── evidence.jsonl
├── stagehand_logs.jsonl
├── result.json
├── final_answer.json
├── final_page_state.json
├── final_screenshot.png
├── runner_label.json
├── run_summary/
│   └── stagehand_flow_index.json
└── step_001/
    ├── agent_input.json
    ├── model_request.json
    ├── model_prompt.txt
    ├── agent_output.json
    ├── action.json
    ├── tool_result.json
    ├── page_state.json
    ├── screenshot.png
    ├── evidence.png
    ├── aria.txt
    └── stagehand_flow/
        ├── stage_summary.json
        ├── 00_ax_tree.txt
        ├── 00_page_text.txt
        ├── 01_hybrid_dom.txt
        ├── 01_hybrid_xpath_map.json
        ├── 01_hybrid_url_map.json
        ├── 01_hybrid_meta.json
        ├── 02_pruned_dom.txt
        ├── 02_pruned_xpath_map.json
        ├── 03_internal_prompt.txt
        ├── 04_internal_llm_request.json
        ├── 05_internal_llm_response.json
        ├── 06_selected_action.json
        └── optional second-step files...
```

## Flow meaning

1. `model_request.json` / `model_prompt.txt` — outer browser-agent model input for this step.
2. `agent_output.json` — outer model response.
3. `action.json` — parsed high-level Stagehand action.
4. `stagehand_flow/01_hybrid_*` — Stagehand page representation and element maps.
5. `stagehand_flow/02_pruned_*` — smaller DOM/tree subset used for internal act planning.
6. `stagehand_flow/03_internal_prompt.txt` — prompt to Stagehand's internal action-selection LLM.
7. `stagehand_flow/04_internal_llm_request.json` — exact internal LLM request.
8. `stagehand_flow/05_internal_llm_response.json` — internal LLM response.
9. `stagehand_flow/06_selected_action.json` — concrete element/action selected by Stagehand.
10. `tool_result.json`, `page_state.json`, screenshots — result/evidence after execution.

If Stagehand needs a second internal act step, the step may also contain:

- `07_second_pruned_dom_diff.txt`
- `08_second_internal_prompt.txt`
- `09_second_internal_llm_request.json`
- `10_second_internal_llm_response.json`
- `11_second_selected_action.json`
