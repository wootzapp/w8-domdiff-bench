# Stagehand native Qatar — clean per-step files

Each `step_XXX_*` folder contains the small set of files for that trajectory step.

| File | Meaning |
|---|---|
| `action.json` | Stagehand trajectory action for this step. |
| `screen.png` | Screenshot for this step. |
| `dom.json` | Stagehand DOM index from CDP `DOM.getDocument`, when DOM capture ran. |
| `ax.txt` | Accessibility tree text, when DOM/AX capture ran. |
| `tree.txt` | Combined Stagehand DOM + accessibility tree. |
| `prune.txt` | Stagehand ariaTree output after its 70k-token cap, for ariaTree steps. |
| `model.txt` | Exact context sent/returned to the relevant model layer for this step. |
| `tool.json` | Short tool result returned to the outer agent, when available. |
| `meta.json` | Source groups and notes for this step. |

Important: Stagehand has two model layers. `ariaTree` returns context to the outer agent model. `act` uses an internal LLM to choose an element, then returns a short result to the outer agent.

## Steps

| Step | Action | DOM? | Files |
|---:|---|---|---|
| 1 | `ariaTree` | yes | action.json, ax.txt, dom.json, model.txt, prune.txt, screen.png, tool.json, tree.txt |
| 2 | `ariaTree` | yes | action.json, ax.txt, dom.json, model.txt, prune.txt, screen.png, tool.json, tree.txt |
| 3 | `think` | no | action.json, screen.png, tool.json |
| 4 | `scroll` | no | action.json, screen.png, tool.json |
| 5 | `ariaTree` | yes | action.json, ax.txt, dom.json, model.txt, prune.txt, screen.png, tool.json, tree.txt |
| 6 | `done` | no | action.json, screen.png, tool.json |
