# agent-browser integration

`client.py` provides browser control through the agent-browser CLI bundled in
w8-core and the browser's CDP input commands. Observation modes and shared
settings are defined in [the datacard](../../../docs/datacard.md).

`AgentBrowserClient.snapshot()` obtains `snapshot -i`, then reads viewport and
reference bounding boxes without scrolling. It keeps only reference lines whose
boxes overlap the viewport, preserving their original executable IDs and complete
accessible labels. Child-frame boxes are translated and clipped. Geometry errors
fail closed. Occlusion is not determined by this filter. The recorder saves the
snapshot as `agent_browser_actions.txt`.

`execute()` requires the recorder CDP client. Current reference clicks use the CLI;
reference scrolls issue hover followed by scroll so nested panes can receive input.
Actions without a reference use CDP navigation, mouse and keyboard commands.
Dispatch results record input delivery. The action schema includes
`navigate`, `back`, `click`, `type`, `press`, `scroll`, `wait`, and
`terminate`; termination is handled by the recorder.

`connect()` and `active_page()` manage the CLI session used for reference actions.
Coordinate actions use CDP without connecting a CLI session. The recorder
captures DOM and screenshot artifacts for each state. The action schema bounds
the commands available to the actor.

The launcher uses the container's CDP port for the CLI and the published host port
for recorder CDP. Container name and CLI command remain configurable. The DOM run
manifest records `action_driver_version`; all runs record browser build provenance,
shared settings and the source hash of the recorder implementation.
