# agent-browser integration

## What this is

The recorder does not implement browser automation. w8-core, a new kind of
browser engine, includes the official
[agent-browser](https://github.com/vercel-labs/agent-browser) CLI at version
0.27.3. The harness invokes that command inside the w8-core container for each
observation and action. Nothing from agent-browser is vendored, forked, or
reimplemented here.

The division of responsibility is fixed:

- **agent-browser owns** observation (the accessibility snapshot and its `@eN`
  ref namespace) and action execution (click, fill, type, scroll, navigate).
- **The recorder owns** ChromiumRL structured capture, screenshots, DOM diffing,
  run artifacts, and the verifier dataset.

`client.py` is the entire integration surface. It translates one validated model
action into one CLI invocation and validates the JSON that comes back. That is
the whole contract, which is why it is one file: the boundary is narrow by
design, and keeping it narrow is what makes the action driver replaceable and
the recordings auditable.

## Runtime use

The Python adapter is self-contained and imports only the standard library. It
does not import `runner.py`, `capture.py`, `recorder_support.py`, or another
recorder module. Its normal runtime needs:

- a running w8-core container;
- the bundled `agent-browser` command; and
- an `AgentBrowserClient` configured with `command`, `session`, `cdp_url`, and
  `timeout`.

```python
from agent_browser import AgentBrowserClient

client = AgentBrowserClient(
    "docker exec w8-core-browser-engine agent-browser",
    session="my-session",
    cdp_url="http://127.0.0.1:9222",
    timeout=30,
)
```

Call `await client.connect()` before taking snapshots or executing actions, and
`await client.close()` when finished. ChromiumRL and recorder modules are not
required for this adapter boundary.

## The two id namespaces

This is the most common source of confusion when reading the code.

- **agent-browser `@eN` refs** are the *executable* namespace. They come from
  `snapshot --interactive`, are the only ids an action may target, and are
  validated against `CaptureBundle.agent_browser_refs` before execution.
- **ChromiumRL numeric ids** are *evidence only*. They appear in captured DOM
  text and are explicitly non-executable; `chromiumrl_evidence_for_model`
  rewrites them before the text reaches the model.

Refs are regenerated on every snapshot. A ref from a previous observation is not
valid in the current one, which is why `action_observation_context` pairs a ref
with the document URL and the control's role/name signature.

## Execution contract

Each model action maps to exactly one CLI invocation, with one documented
exception: **ref-targeted scroll issues `hover <ref>` followed by
`scroll <direction> <pixels>`**. Version 0.27.3's `scroll --selector` accepts CSS,
not `@eN`, so hovering places the pointer over the element and the subsequent
wheel event dispatches to whatever is under it. This means one recorded step can
contain two CLI operations, and the hover itself may change the page. Tracked as
a known limitation.

## Version and provenance

The default command is `docker exec w8-core-browser-engine agent-browser`. The
container name and command remain configurable through `CONTAINER_NAME` and
`AGENT_BROWSER_COMMAND`. The task launcher reads `CDP_PORT` from the running
container. Direct runner use can set `AGENT_BROWSER_CDP_URL`; its default is
`http://127.0.0.1:9222`.

The version in use is recorded in every run:

- `manifest.json` → `action_driver.command`, `action_driver.version`
- each `action.json` → `model_input_agent_browser.version`

Anyone auditing a recording can determine exactly which driver produced it.

## Exposed action surface

Nine browser actions are reachable by the model: `navigate`, `back`, `click`,
`fill`, `type`, `select`, `press`, `scroll`, `wait`. (`request_human` and
`terminate` are recorder-level, not browser operations.)

agent-browser 0.27.3 exposes substantially more. The unexposed surface is not an
oversight — adding an action requires changes to `ACTION_SCHEMA`,
`client.execute`, and `WEBSURFER_ACTION_MAP`, and the export string must be
confirmed with the verifier.

Two exclusions are deliberate and should stay:

- **`eval`** — arbitrary JavaScript would break the property that every recorded
  action is atomic and replayable from its arguments alone.
- **`find` semantic locators** — a second targeting namespace alongside `@eN`
  would require per-action provenance recording what resolved the target.

## Known limitations

- `hover`+`scroll` for ref-targeted scrolling (above). 0.27.3 offers no
  single-command ref-based wheel.
- Parallel sessions can contend for tabs in 0.27.3; `active_page()` requires
  exactly one active page tab and fails loudly otherwise. Not observed in any
  recording to date. Fixed upstream in 0.34.0 via `--pin-tab`; upgrading would
  break comparability with existing recordings.

Adjust the limitations section as items resolve — that's the part that goes stale.
